"""8.4 Sales Forecasting — scenario views (what-if modelling that never mutates the forecast).

Every queryset is `tenant=request.tenant`-scoped; `request.tenant` is `None` for the `admin`
superuser and an empty register is the correct answer for them (multi-tenancy rule 1/2),
never an `.all()`.

Three structural rulings are enforced here rather than in the template:

* **A scenario never mutates a `ForecastSubmission`.** `forecast_scenario_apply` writes
  `projected_commit_amount`, `projected_total_amount` and the two booleans on the
  `ForecastScenario` row and nothing else -- the baseline call is *read* to compute the
  projection, never written (contract 0.6 / 3.4). The isolation note rendered on the detail
  page says so in the manager's own words.
* **`is_selected` is workflow-owned.** `forecast_scenario_select` is the only writer, and it
  is a **transactional state flip**, not a form field: only the baseline may be selected, and
  every other row for the tenant is cleared in the same transaction so a POST can never leave
  two rows claiming to be the current plan (the `sales_fsc_baseline_selected` CheckConstraint
  makes the baseline half structural; this makes the *single*-selected half so).
* **Scenarios ship no export action** (contract 13.10), so there is deliberately no
  `export_url` context key and no export button -- rendering one would be a template bug.

`forecast_org_unit_chain` is imported from the adjustment module rather than copied: there is
no `User.manager` field anywhere, so the rep -> manager -> director walk is
`core.OrgUnit.parent`, which has no cycle validation, and that walk is already iterative,
depth-bounded and seen-set guarded.
"""
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from apps.core.crud import apply_search, as_db_int, paginate
from apps.core.utils import write_audit_log
from apps.sales.forms.SalesForecasting.ForecastScenarios import (
    APPLY_TARGET_CHOICES,
    DEFAULT_VARIANCE_THRESHOLD_PCT,
    ForecastScenarioApplyForm,
    ForecastScenarioForm,
)
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.SalesForecasting.ForecastScenarios import ForecastScenario
from apps.sales.models.SalesForecasting.ForecastSubmissions import CATEGORY_AMOUNT_FIELDS
from apps.sales.forecast_services import forecast_org_unit_chain
from apps.sales.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "sales/salesforecasting/forecastscenario/list.html"
TEMPLATE_DETAIL = "sales/salesforecasting/forecastscenario/detail.html"
TEMPLATE_FORM = "sales/salesforecasting/forecastscenario/form.html"

#: Rendered verbatim on the detail page. Stated where the manager will actually read it,
#: because "will applying this change my numbers?" is the only question a scenario raises.
ISOLATION_NOTE = (
    "Applying a scenario never changes a forecast call. It records this scenario's own "
    "projection beside the deltas that produced it; every rep's committed, best-case and "
    "pipeline figures stay exactly as they were submitted."
)


def _is_tenant_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _tenant_owners(tenant):
    """The active users of one tenant, tenant-scoped (R2 -- never ``User.objects.all()``)."""
    from apps.accounts.models import User

    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True)


def _scenario_queryset(request):
    return ForecastScenario.objects.filter(tenant=request.tenant).select_related(
        "period", "owner",
    )


def _filter_scenario_queryset(request, queryset):
    """Parse GET and apply every filter BEFORE pagination (L11 on both param kinds)."""
    filters = {
        "q": request.GET.get("q", "").strip()[:200],
        "scenario_type": request.GET.get("scenario_type", "").strip(),
        "period_id": as_db_int(request.GET.get("period_id", "")),
        "owner_id": as_db_int(request.GET.get("owner_id", "")),
        "is_selected": request.GET.get("is_selected", "").strip(),
    }
    # A junk enum resets to "" so a stale bookmark shows the unfiltered register rather than
    # an empty one. The enum is validated against the model's own CHOICES, never a local list.
    if filters["scenario_type"] not in dict(ForecastScenario.SCENARIO_TYPE_CHOICES):
        filters["scenario_type"] = ""
    if filters["is_selected"] not in ("yes", "no", ""):
        filters["is_selected"] = ""
    queryset = apply_search(
        queryset, filters["q"], ["number", "name", "assumption_notes"],
    )
    if filters["scenario_type"]:
        queryset = queryset.filter(scenario_type=filters["scenario_type"])
    if filters["is_selected"] == "yes":
        queryset = queryset.filter(is_selected=True)
    elif filters["is_selected"] == "no":
        queryset = queryset.filter(is_selected=False)
    # Integer FK params go through as_db_int, so ?period_id=abc and an over-range
    # ?period_id=999...9 are SKIPPED rather than 500 (L11).
    for param in ("period_id", "owner_id"):
        number = filters[param]
        if number is not None and number != 0:
            queryset = queryset.filter(**{param: number})
    return queryset, filters


def _filter_choices(tenant):
    """The bounded FK lists the list and form dropdowns read.

    Returned as ``{"pk", "label"}`` dicts rather than hydrated rows: a scenario page only ever
    needs an id and a label per period / owner, and that is the same page-weight bound the
    sibling list views use. ``[]`` for a ``None`` tenant, never ``.all()``.
    """
    if tenant is None:
        return [], []
    periods = [
        {"pk": pk, "label": label}
        for pk, label in ForecastPeriod.objects.filter(tenant=tenant).order_by(
            "-period_year", "period_number", "name",
        ).values_list("pk", "number")[:200]
    ]
    owners = [
        {"pk": pk, "label": (first or username) if not last else f"{first} {last}".strip()}
        for pk, first, last, username in _tenant_owners(tenant).order_by(
            "username",
        ).values_list("pk", "first_name", "last_name", "username")[:500]
    ]
    return periods, owners


def _baseline_totals(obj):
    """The five category amounts of the call this scenario projects -- the deltas' input.

    ``None`` for every bucket when the period has no forecast call at all, which is the honest
    answer: there is nothing to project, and the template renders an em dash rather than five
    confident zeros.
    """
    submission = obj.baseline_submission()
    if submission is None:
        return {value: None for value, _ in CATEGORY_AMOUNT_FIELDS}
    return {
        value: Decimal(getattr(submission, field, 0) or 0)
        for value, field in CATEGORY_AMOUNT_FIELDS
    }


def _owner_org_unit(user, tenant):
    """The owner's node on the rollup axis, or ``None``.

    There is no `User.manager` to read, so ``sales.OpportunityTeamMember.org_unit`` is the only
    link between a person and the org hierarchy. The chain walk itself is
    ``forecast_org_unit_chain``, imported from the adjustment module: ``core.OrgUnit.parent``
    is a self-FK with no cycle validation, and that walk is already iterative, depth-bounded
    and seen-set guarded. A second copy of it would be a second thing to get wrong.
    """
    if tenant is None or user is None or not getattr(user, "pk", None):
        return None
    membership = (
        OpportunityTeamMember.objects.filter(
            tenant=tenant, user=user, is_active=True, org_unit__isnull=False,
        ).select_related("org_unit").order_by("id").first()
    )
    return membership.org_unit if membership is not None else None


def _scenario_permissions(obj, request):
    """Who may do what on this scenario, re-derived server-side (never template-side).

    A locked period freezes the what-ifs as well as the calls; and only the **baseline** may be
    selected, which is the constraint ``forecast_scenario_select`` enforces transactionally.
    """
    is_admin = _is_tenant_admin(request.user)
    period_locked = bool(obj.period_id and obj.period.is_locked)
    return {
        "can_edit": is_admin and not period_locked,
        "can_delete": is_admin and not period_locked,
        "can_apply": is_admin and not period_locked,
        # Selecting is a baseline-only right: `sales_fsc_baseline_selected` forbids any other
        # row from being selected, so the button is offered under exactly that condition.
        "can_select": is_admin and not period_locked and obj.is_baseline and not obj.is_selected,
        "is_period_locked": period_locked,
        "owns": obj.owner_id == request.user.pk,
    }


@login_required
def forecast_scenario_list(request):
    base = _scenario_queryset(request)
    queryset, filters = _filter_scenario_queryset(request, base)
    page_obj = paginate(request, queryset, 20)
    periods, owners = _filter_choices(request.tenant)
    stats = base.aggregate(
        total=Count("pk"),
        upside=Count("pk", filter=Q(scenario_type="upside")),
        base=Count("pk", filter=Q(scenario_type="base")),
        downside=Count("pk", filter=Q(scenario_type="downside")),
        custom=Count("pk", filter=Q(scenario_type="custom")),
        selected=Count("pk", filter=Q(is_selected=True)),
    )
    # Deliberately NO `export_url`: scenarios ship no export action (contract 13.10), and a
    # template that rendered one would be reading a key the view never passes.
    return render(request, TEMPLATE_LIST, {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": filters["q"],
        "scenario_type": filters["scenario_type"],
        "period_id": filters["period_id"] or "",
        "owner_id": filters["owner_id"] or "",
        "is_selected": filters["is_selected"],
        "scenario_type_choices": ForecastScenario.SCENARIO_TYPE_CHOICES,
        "periods": periods,
        "owners": owners,
        "selected_choices": [("yes", "Selected"), ("no", "Not selected")],
        "stats": stats,
        "can_edit_all": _is_tenant_admin(request.user),
    })


@login_required
def forecast_scenario_detail(request, pk):
    obj = get_object_or_404(_scenario_queryset(request), pk=pk)
    permissions = _scenario_permissions(obj, request)
    periods, owners = _filter_choices(request.tenant)
    org_unit = _owner_org_unit(obj.owner, obj.tenant_id)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "period": obj.period if obj.period_id else None,
        "owner": obj.owner,
        # The PROPERTIES, never a column: each is None when the period has no call to
        # project, which renders as an em dash rather than a fake 0.00.
        "effective_pipeline_amount": obj.effective_pipeline_amount,
        "effective_best_case_amount": obj.effective_best_case_amount,
        "effective_commit_amount": obj.effective_commit_amount,
        "baseline_totals": _baseline_totals(obj),
        "baseline_submission": obj.baseline_submission(),
        "periods": periods,
        "owners": owners,
        "scenario_type_choices": ForecastScenario.SCENARIO_TYPE_CHOICES,
        "can_apply": permissions["can_apply"],
        "can_select": permissions["can_select"],
        "can_edit": permissions["can_edit"],
        "can_delete": permissions["can_delete"],
        "is_period_locked": permissions["is_period_locked"],
        # The rollup axis for this scenario's owner, from the shared cycle-safe walk.
        "owner_org_unit": org_unit,
        "owner_org_chain": forecast_org_unit_chain(org_unit) if org_unit is not None else [],
        "apply_form": ForecastScenarioApplyForm(
            initial={"period": obj.period_id, "target": "commit"}, tenant=request.tenant,
        ),
        "isolation_note": ISOLATION_NOTE,
    })


def _form_context(request, form, is_edit, obj=None):
    """The pinned create/edit context (contract 6.4) -- every key the template reads."""
    periods, owners = _filter_choices(request.tenant)
    selected_period = None
    if obj is not None and obj.period_id:
        selected_period = obj.period
    elif form.is_bound and form.data.get("period"):
        selected_period = ForecastPeriod.objects.filter(
            tenant=request.tenant, pk=as_db_int(form.data.get("period")),
        ).first()
    return {
        "form": form,
        "is_edit": is_edit,
        "obj": obj,
        "periods": periods,
        "owners": owners,
        "scenario_type_choices": ForecastScenario.SCENARIO_TYPE_CHOICES,
        "is_period_locked": bool(selected_period is not None and selected_period.is_locked),
    }


def _attach_save_error(form, exc):
    """Route a model-level save refusal onto the right form field, or the form itself."""
    if isinstance(exc, ValidationError) and hasattr(exc, "error_dict"):
        for field_name, errors in exc.message_dict.items():
            for error in errors:
                form.add_error(field_name if field_name in form.fields else None, error)
        return
    form.add_error(
        None, "That scenario could not be saved. Check the period, the name and the deltas.",
    )


def _refuse_message(exc):
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)[:300] or "That scenario cannot be changed."
    return "That scenario could not be saved."


@tenant_admin_required
def forecast_scenario_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ForecastScenarioForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.tenant = request.tenant
                    # Baseline implies selected, settled in one place so a crafted POST cannot
                    # write a baseline that is not the plan (the CheckConstraint's other half).
                    obj.sync_selected_from_baseline()
                    # A brand-new baseline displaces the previous one for this period: exactly
                    # one selected scenario per period is the invariant the select action and
                    # this creation path both maintain.
                    if obj.is_baseline:
                        ForecastScenario.objects.filter(
                            tenant=request.tenant, period_id=obj.period_id,
                        ).exclude(pk=obj.pk).update(is_baseline=False, is_selected=False)
                    obj.full_clean()
                    obj.save()
                    obj.snapshot_projection()
                    obj.save(update_fields=["projected_commit_amount", "projected_total_amount"])
                    write_audit_log(
                        request.user, obj, "create",
                        {
                            "operation": "create_scenario",
                            "scenario": str(obj)[:200],
                            "scenario_type": str(obj.scenario_type)[:200],
                            "is_baseline": obj.is_baseline,
                        },
                        tenant=request.tenant,
                    )
            except (ValidationError, IntegrityError) as exc:
                _attach_save_error(form, exc)
                return render(request, TEMPLATE_FORM, _form_context(request, form, False))
            messages.success(request, "Scenario created. The real forecast is untouched.")
            return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    else:
        form = ForecastScenarioForm(tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, False))


@tenant_admin_required
def forecast_scenario_edit(request, pk):
    obj = get_object_or_404(_scenario_queryset(request), pk=pk)
    if obj.period_id and obj.period.is_locked:
        messages.error(request, "The period is locked, so its scenarios are read-only.")
        return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    if request.method == "POST":
        form = ForecastScenarioForm(
            request.POST, instance=obj, tenant=request.tenant, user=request.user,
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated = form.save(commit=False)
                    updated.tenant = request.tenant
                    updated.sync_selected_from_baseline()
                    updated.full_clean()
                    updated.save()
                    # The projection follows the deltas, so a changed delta is never left
                    # beside a stale snapshot. Still only writes this row.
                    updated.snapshot_projection()
                    updated.save(update_fields=["projected_commit_amount", "projected_total_amount"])
                    write_audit_log(
                        request.user, updated, "update",
                        {
                            "operation": "update_scenario",
                            "scenario": str(updated)[:200],
                            "pipeline_delta_pct": str(updated.pipeline_delta_pct)[:200],
                            "commit_delta_pct": str(updated.commit_delta_pct)[:200],
                        },
                        tenant=request.tenant,
                    )
            except (ValidationError, IntegrityError) as exc:
                _attach_save_error(form, exc)
                return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))
            messages.success(request, "Scenario updated. The real forecast is untouched.")
            return redirect("sales:forecast_scenario_detail", pk=updated.pk)
    else:
        form = ForecastScenarioForm(instance=obj, tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))


@require_POST
@tenant_admin_required
def forecast_scenario_select(request, pk):
    """Make this scenario the selected one -- a state flag, and only ever the baseline's.

    This is the single writer of ``is_selected`` (contract 13.4), and it is **hand-rolled on
    purpose** rather than a ``crud_*`` helper, so it can maintain the invariant the
    CheckConstraint alone cannot: ``sales_fsc_baseline_selected`` guarantees a baseline IS
    selected, but nothing in the schema stops a *second* baseline from being selected too. So
    every other scenario for the tenant is cleared in the SAME transaction as the one being
    promoted, with ``select_for_update`` holding the rows while it happens. A POST therefore
    cannot leave two rows claiming to be the current plan, and a partial failure rolls the
    whole flip back.
    """
    obj = get_object_or_404(_scenario_queryset(request), pk=pk)
    if obj.period_id and obj.period.is_locked:
        messages.error(request, "The period is locked, so its scenarios are read-only.")
        return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    # Only the baseline may be selected. Refused here, server-side, rather than as a hidden
    # button -- the constraint and the action must never disagree about who is eligible.
    if not obj.is_baseline:
        messages.error(
            request,
            "Only the baseline scenario can be the current plan. Make this one the baseline first.",
        )
        return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    try:
        with transaction.atomic():
            locked = ForecastScenario.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            # Clear every other scenario first, then promote this one. A unique index, were
            # there one, could not express this: the constraint is per-row, not per-set.
            ForecastScenario.objects.filter(
                tenant=request.tenant, is_selected=True,
            ).exclude(pk=locked.pk).update(is_selected=False)
            locked.is_baseline = True
            locked.is_selected = True
            locked.full_clean()
            locked.save(update_fields=["is_baseline", "is_selected", "updated_at"])
            write_audit_log(
                request.user, locked, "update",
                {
                    "operation": "select_scenario",
                    "scenario": str(locked)[:200],
                    "note": "Application state only; no forecast call was modified.",
                },
                tenant=request.tenant,
            )
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _refuse_message(exc))
        return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    messages.success(request, "This scenario is now the current plan. No forecast call was changed.")
    return redirect("sales:forecast_scenario_detail", pk=obj.pk)


def _apply_target_amount(obj, target):
    """The figure a scenario is judged against, for the chosen ``target``.

    Read-only: it reads the baseline call and the scenario's own deltas and returns a number.
    No row is written here, which is the isolation rule again at the level of the helper.
    """
    if target == "commit":
        return obj.effective_commit_amount
    if target == "total":
        parts = (
            obj.effective_pipeline_amount,
            obj.effective_best_case_amount,
            obj.effective_commit_amount,
        )
        if any(part is None for part in parts):
            return None
        return sum(parts, Decimal("0")).quantize(Decimal("0.01"))
    # "weighted": the baseline call's own service snapshot, unprojected -- a scenario moves the
    # three user-entered lines, and the weighted figure is the pipeline's, not the plan's.
    submission = obj.baseline_submission()
    return Decimal(submission.weighted_amount or 0) if submission is not None else None


def _baseline_target_amount(obj, target):
    """The **unprojected** figure for a target: the real forecast, before any delta.

    This is the "before" side of the variance the apply action reports, and it is read
    straight off the baseline call -- never written, which is the isolation rule again.
    """
    submission = obj.baseline_submission()
    if submission is None:
        return None
    if target == "commit":
        return Decimal(submission.commit_amount or 0)
    if target == "total":
        return submission.total_forecast_amount
    return Decimal(submission.weighted_amount or 0)


def _variance_pct(before, after):
    """Move from ``before`` to ``after`` as a percentage, or ``None`` when unmeasurable.

    ``None`` rather than a division when the baseline is zero: "it moved off nothing" is not
    a percentage, and ``Infinity`` must never reach a template (the ``attainment_pct`` rule).
    """
    if before is None or after is None or Decimal(before) == 0:
        return None
    return (
        (Decimal(after) - Decimal(before)) / Decimal(before) * Decimal("100")
    ).quantize(Decimal("0.01"))


@require_POST
@tenant_admin_required
def forecast_scenario_apply(request):
    """Recompute every scenario's projection for one period -- and touch nothing else.

    This is the isolation rule in its most load-bearing form. The body below writes exactly two
    columns, ``projected_commit_amount`` and ``projected_total_amount``, plus the ``is_selected``
    flag, on ``ForecastScenario`` rows. There is deliberately **no** ``ForecastSubmission``
    write anywhere in this function: the baseline call is read to seed the arithmetic and the
    result lands on the scenario. Contract 0.6 makes the smoke sweep assert that applying a
    scenario leaves every submission row byte-identical.
    """
    form = ForecastScenarioApplyForm(request.POST or None, tenant=request.tenant)
    if not form.is_valid():
        messages.error(
            request,
            "; ".join(
                error for errors in form.errors.values() for error in errors
            )[:300] or "Choose a period before applying the scenarios.",
        )
        return redirect("sales:forecast_scenario_list")
    period = form.cleaned_data["period"]
    target = form.cleaned_data["target"]
    threshold = form.cleaned_data.get("variance_threshold_pct") or DEFAULT_VARIANCE_THRESHOLD_PCT
    try:
        with transaction.atomic():
            locked_period = ForecastPeriod.objects.select_for_update().get(
                pk=period.pk, tenant=request.tenant,
            )
            if locked_period.is_locked:
                messages.error(request, "The period is locked, so its scenarios are read-only.")
                return redirect("sales:forecast_scenario_list")
            applied, moved = 0, 0
            for obj in (
                ForecastScenario.objects.select_for_update()
                .filter(tenant=request.tenant, period_id=locked_period.pk)
                .order_by("pk")
            ):
                obj.snapshot_projection()
                obj.sync_selected_from_baseline()
                obj.save(update_fields=[
                    "projected_commit_amount", "projected_total_amount",
                    "is_selected", "updated_at",
                ])
                applied += 1
                # How far this scenario's projection sits from the real forecast it models,
                # reported rather than blocked: the snapshot is already written, and a wild
                # delta should be visible rather than silent.
                variance = _variance_pct(
                    _baseline_target_amount(obj, target), _apply_target_amount(obj, target),
                )
                if variance is not None and abs(variance) > Decimal(threshold):
                    moved += 1
            write_audit_log(
                request.user, None, "update",
                {
                    "operation": "apply_scenarios",
                    "period": str(locked_period)[:200],
                    "target": str(target)[:200],
                    "variance_threshold_pct": str(threshold)[:200],
                    "scenarios_applied": applied,
                    "scenarios_beyond_threshold": moved,
                    "note": "Scenario projections only; no forecast call was modified.",
                },
                tenant=request.tenant,
            )
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _refuse_message(exc))
        return redirect("sales:forecast_scenario_list")
    if moved:
        messages.warning(
            request,
            f"Applied {applied} projection(s); {moved} sit further than {threshold}% from the "
            f"{dict(APPLY_TARGET_CHOICES).get(target, target)} they model. "
            "The real forecast is untouched.",
        )
    else:
        messages.success(
            request, f"Applied {applied} scenario projection(s). The real forecast is untouched.",
        )
    return redirect("sales:forecast_scenario_list")


@require_POST
@tenant_admin_required
def forecast_scenario_delete(request, pk):
    obj = get_object_or_404(_scenario_queryset(request), pk=pk)
    if obj.period_id and obj.period.is_locked:
        messages.error(request, "The period is locked, so its scenarios are read-only.")
        return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    try:
        with transaction.atomic():
            locked = ForecastScenario.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            write_audit_log(
                request.user, locked, "delete",
                {
                    "action": "forecast_scenario",
                    "scenario": str(locked)[:200],
                    "is_baseline": locked.is_baseline,
                },
                tenant=request.tenant,
            )
            locked.delete()
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _refuse_message(exc))
        return redirect("sales:forecast_scenario_detail", pk=obj.pk)
    messages.success(request, "Scenario deleted.")
    return redirect("sales:forecast_scenario_list")
