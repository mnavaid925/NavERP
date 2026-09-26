"""8.4 Sales Forecasting — manager override views.

Every queryset is `tenant=request.tenant`-scoped; `request.tenant` is `None` for the
`admin` superuser and an empty register is the correct answer for them (multi-tenancy
rule 1/2), never an `.all()`.

Two structural rulings are enforced here rather than in the template:

* **The system value is never stored, only the applied delta.** `original_value` /
  `original_category` are snapshotted on the create path from the submission and the
  targeted deal; the post-override figure is never written. That is precisely what makes
  Reset always possible -- `forecast_adjustment_revert` flips a flag and stamps a reason,
  and there is no cached "current" figure left stale by the flip.
* **The reason is the signal.** `reason_code` is enforced in the form's `clean()` and a
  Reset demands `revert_reason` (Dynamics' mandatory-reason Reset), both server-side.

`forecast_org_unit_chain` is the rollup walk this pass owns (contract 8): the rep ->
manager -> director axis runs on `core.OrgUnit.parent`, which has **no cycle validation
anywhere in the codebase**, so the walk is iterative, depth-bounded and carries a seen-set.
"""
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import apply_search, as_db_int, paginate
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.SalesForecasting.ForecastAdjustments import (
    ForecastAdjustmentForm,
    ForecastRevertForm,
)
from apps.sales.models.OpportunityPipeline.Pipelines import OpportunityPipelinePlacement
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember
from apps.sales.models.SalesForecasting.ForecastAdjustments import ForecastAdjustment
from apps.sales.models.SalesForecasting.ForecastSubmissions import ForecastSubmission
from apps.sales.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "sales/salesforecasting/forecastadjustment/list.html"
TEMPLATE_DETAIL = "sales/salesforecasting/forecastadjustment/detail.html"
TEMPLATE_FORM = "sales/salesforecasting/forecastadjustment/form.html"

#: Hard cap on the OrgUnit walk. A hierarchy deeper than this is treated as unresolvable
#: rather than walked: a legacy cycle must not become an infinite loop.
ORG_UNIT_CHAIN_MAX_DEPTH = 12


def _is_tenant_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def forecast_org_unit_chain(org_unit, max_depth=ORG_UNIT_CHAIN_MAX_DEPTH):
    """The chain of `core.OrgUnit` nodes from `org_unit` up to its root, root last.

    There is **no `User.manager` field** anywhere in this codebase, so the rep -> manager ->
    director walk is the `OrgUnit.parent` self-FK. Three hazards, all handled here:

    * `parent` is a self-FK with **no cycle validation anywhere**, so a legacy A->B->A row
      is reachable. A `seen` set of pks stops it instead of hanging the request.
    * the walk is **iterative**, never recursive, so a deep chain cannot blow the stack.
    * it is **depth-bounded**; a chain past the cap is truncated rather than followed.

    Returns `[]` for `None`, so every caller can iterate the result unguarded.
    """
    chain, seen, node, depth = [], set(), org_unit, 0
    while node is not None and depth < max_depth:
        if node.pk in seen:
            break
        seen.add(node.pk)
        chain.append(node)
        node = node.parent
        depth += 1
    return chain


def _acting_org_unit(user, tenant):
    """The acting user's node, resolved through `sales.OpportunityTeamMember.org_unit`.

    There is no `User.manager` to read, so the membership row is the only link between a
    person and the org hierarchy. `None` when the user holds no active membership, which the
    level check treats as "cannot prove a violation" rather than as a denial.
    """
    if tenant is None or user is None or not getattr(user, "pk", None):
        return None
    membership = (
        OpportunityTeamMember.objects.filter(
            tenant=tenant, user=user, is_active=True, org_unit__isnull=False,
        )
        .select_related("org_unit")
        .order_by("id")
        .first()
    )
    return membership.org_unit if membership is not None else None


def _adjusts_above_acting_level(user, submission):
    """True when the acting user is overriding a node **above** their own.

    Microsoft's rule: "you cannot adjust a level above you". A submission whose org unit is
    a strict ancestor of the acting user's own node is a violation; the user's own node and
    any branch that is not an ancestor are both fine. This is a **business rule over a role
    check, not a record ACL** (contract 8) -- a tenant admin passes it unconditionally.
    """
    if _is_tenant_admin(user):
        return False
    acting = _acting_org_unit(user, submission.tenant_id)
    target = submission.org_unit
    if acting is None or target is None or acting.pk == target.pk:
        return False
    ancestor_pks = {node.pk for node in forecast_org_unit_chain(acting)}
    return target.pk in ancestor_pks



def _adjustment_queryset(request):
    return ForecastAdjustment.objects.filter(tenant=request.tenant).select_related(
        "submission", "submission__period", "opportunity", "placement", "created_by",
    )


def _filter_adjustment_queryset(request, queryset):
    """Parse GET and apply every filter BEFORE pagination (L11 on both param kinds)."""
    filters = {
        "q": request.GET.get("q", "").strip()[:200],
        "kind": request.GET.get("kind", "").strip(),
        "reason_code": request.GET.get("reason_code", "").strip(),
        "target_field": request.GET.get("target_field", "").strip(),
        "is_reverted": request.GET.get("is_reverted", "").strip(),
        "submission_id": as_db_int(request.GET.get("submission_id", "")),
        "opportunity_id": as_db_int(request.GET.get("opportunity_id", "")),
    }
    # A junk enum resets to "" so a stale bookmark shows the unfiltered register rather than
    # an empty one.
    if filters["kind"] not in dict(ForecastAdjustment.ADJUSTMENT_KIND_CHOICES):
        filters["kind"] = ""
    if filters["reason_code"] not in dict(ForecastAdjustment.REASON_CODE_CHOICES):
        filters["reason_code"] = ""
    if filters["target_field"] not in dict(ForecastAdjustment.TARGET_FIELD_CHOICES):
        filters["target_field"] = ""
    if filters["is_reverted"] not in ("yes", "no"):
        filters["is_reverted"] = ""
    queryset = apply_search(
        queryset, filters["q"], ["number", "reason_code", "revert_reason", "note"],
    )
    if filters["kind"]:
        queryset = queryset.filter(adjustment_kind=filters["kind"])
    if filters["reason_code"]:
        queryset = queryset.filter(reason_code=filters["reason_code"])
    if filters["target_field"]:
        queryset = queryset.filter(target_field=filters["target_field"])
    if filters["is_reverted"] == "yes":
        queryset = queryset.filter(is_reverted=True)
    elif filters["is_reverted"] == "no":
        queryset = queryset.filter(is_reverted=False)
    # Integer FK params go through as_db_int, so ?submission_id=abc and an over-range
    # ?submission_id=999...9 are SKIPPED rather than 500 (L11).
    for param, lookup in (
        ("submission_id", "submission_id"),
        ("opportunity_id", "opportunity_id"),
    ):
        number = filters[param]
        if number is not None and number != 0:
            queryset = queryset.filter(**{lookup: number})
    return queryset, filters


def _filter_choices(tenant):
    """The bounded FK lists the list and form dropdowns read.

    An adjustment page only ever needs an id and a label per row, so submissions and
    opportunities are returned as ``{"pk", "label"}`` dicts rather than fully hydrated
    rows -- the same page-weight bound the sibling list view uses.
    """
    if tenant is None:
        return [], []
    submissions = [
        {"pk": pk, "label": label}
        for pk, label in ForecastSubmission.objects.filter(tenant=tenant).order_by(
            "-period__period_year", "period__period_number", "number",
        ).values_list("pk", "number")[:200]
    ]
    opportunities = [
        {"pk": pk, "label": label}
        for pk, label in Opportunity.objects.filter(tenant=tenant)
        .order_by("name").values_list("pk", "name")[:500]
    ]
    return submissions, opportunities


def _placements_for(tenant, opportunity_id):
    """The placements belonging to one deal -- ``[]`` when no deal is chosen yet.

    ``OpportunityPipelinePlacement`` is a OneToOne on the opportunity, so this is at most one
    row; returning a list keeps the template's dropdown loop uniform.
    """
    if tenant is None or not opportunity_id:
        return []
    return list(
        OpportunityPipelinePlacement.objects.filter(
            tenant=tenant, opportunity_id=opportunity_id,
        ).select_related("pipeline", "current_stage")[:500]
    )


def _selected_opportunity_id(request, obj=None):
    """The deal the form is currently pointed at: the POST, else the bound instance."""
    if request.method == "POST" and request.POST.get("opportunity"):
        return as_db_int(request.POST.get("opportunity"))
    return obj.opportunity_id if obj is not None else None


@login_required
def forecast_adjustment_list(request):
    base = _adjustment_queryset(request)
    queryset, filters = _filter_adjustment_queryset(request, base)
    page_obj = paginate(request, queryset, 20)
    submissions, opportunities = _filter_choices(request.tenant)
    stats = base.aggregate(
        total=Count("pk"),
        direct=Count("pk", filter=Q(adjustment_kind="direct")),
        indirect=Count("pk", filter=Q(adjustment_kind="indirect")),
        revert=Count("pk", filter=Q(adjustment_kind="revert")),
        reverted=Count("pk", filter=Q(is_reverted=True)),
        unreverted=Count("pk", filter=Q(is_reverted=False)),
    )
    export_url = reverse("sales:forecast_adjustment_export")
    if request.GET.urlencode():
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, TEMPLATE_LIST, {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": filters["q"],
        "kind": filters["kind"],
        "reason_code": filters["reason_code"],
        "target_field": filters["target_field"],
        "submission_id": filters["submission_id"] or "",
        "opportunity_id": filters["opportunity_id"] or "",
        "is_reverted": filters["is_reverted"],
        "adjustment_kind_choices": ForecastAdjustment.ADJUSTMENT_KIND_CHOICES,
        "reason_code_choices": ForecastAdjustment.REASON_CODE_CHOICES,
        "target_field_choices": ForecastAdjustment.TARGET_FIELD_CHOICES,
        "category_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
        "submissions": submissions,
        "opportunities": opportunities,
        "reverted_choices": [("yes", "Reverted"), ("no", "Not reverted")],
        "stats": stats,
        "export_url": export_url,
        "can_edit_all": _is_tenant_admin(request.user),
    })


def _display_value(row, prefix):
    """One of ``original_display`` / ``adjusted_display`` -- a value OR a category label.

    ``prefix`` is ``"original"`` or ``"adjusted"``; which of the two stored pairs is read
    follows the row's own ``target_field``. Resolved here so the template never branches on
    ``target_field`` itself and a category row never prints a bare enum value.
    """
    if row.target_field == "amount":
        value = getattr(row, f"{prefix}_value", None)
        return value if value is not None else "—"
    category = getattr(row, f"{prefix}_category", None)
    if not category:
        return "—"
    return dict(Opportunity.FORECAST_CATEGORY_CHOICES).get(category, category)


@login_required
def forecast_adjustment_detail(request, pk):
    obj = get_object_or_404(_adjustment_queryset(request), pk=pk)
    is_admin = _is_tenant_admin(request.user)
    period_locked = bool(
        obj.submission_id and obj.submission.period_id and obj.submission.period.is_locked
    )
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "submission": obj.submission,
        "opportunity": obj.opportunity,
        "placement": obj.placement,
        "created_by": obj.created_by,
        # The PROPERTY, not a column: `None` for a category row, which renders as an em dash.
        "net_delta": obj.net_delta,
        "original_display": _display_value(obj, "original"),
        "adjusted_display": _display_value(obj, "adjusted"),
        "reason_code_choices": ForecastAdjustment.REASON_CODE_CHOICES,
        "adjustment_kind_choices": ForecastAdjustment.ADJUSTMENT_KIND_CHOICES,
        "target_field_choices": ForecastAdjustment.TARGET_FIELD_CHOICES,
        "category_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
        "revert_form": ForecastRevertForm(tenant=request.tenant),
        # An already-reset row is history: re-editing it would rewrite a closed audit entry.
        "can_revert": is_admin and not obj.is_reverted and not period_locked,
        "can_edit": is_admin and not obj.is_reverted and not period_locked,
        "can_delete": is_admin and not obj.is_reverted,
        "is_reverted": obj.is_reverted,
        "revert_reason": obj.revert_reason,
        "reverted_at": obj.reverted_at,
        "is_period_locked": period_locked,
    })


def _form_context(request, form, is_edit, obj=None):
    """The pinned create/edit context (contract 6.3).

    ``placements`` is narrowed to the currently chosen deal, so the dropdown can never offer
    a placement belonging to a different opportunity; it is ``[]`` on create because no deal
    has been picked yet.
    """
    submissions, opportunities = _filter_choices(request.tenant)
    submission = None
    if obj is not None and obj.submission_id:
        submission = obj.submission
    elif request.method == "POST" and request.POST.get("submission"):
        submission = ForecastSubmission.objects.filter(
            tenant=request.tenant, pk=as_db_int(request.POST.get("submission")),
        ).first()
    return {
        "form": form,
        "is_edit": is_edit,
        "obj": obj,
        "submissions": submissions,
        "opportunities": opportunities,
        "placements": _placements_for(
            request.tenant, _selected_opportunity_id(request, obj),
        ),
        "adjustment_kind_choices": ForecastAdjustment.ADJUSTMENT_KIND_CHOICES,
        "target_field_choices": ForecastAdjustment.TARGET_FIELD_CHOICES,
        "reason_code_choices": ForecastAdjustment.REASON_CODE_CHOICES,
        "category_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
        "is_period_locked": bool(
            submission is not None and submission.period_id and submission.period.is_locked
        ),
    }


def _snapshot_system_value(obj, submission):
    """Snapshot what the forecast said BEFORE the override. Never the post-override figure.

    This is the one place the "before" number enters the system, and it is written by the
    server from the submission and the targeted deal -- never typed by the user. Because only
    the delta is stored alongside it, Reset is always possible: there is no cached current
    value left stale by the flip.
    """
    if obj.target_field == "amount":
        source = Decimal(submission.commit_amount or 0) if submission is not None else Decimal(0)
        if obj.opportunity_id:
            source = Decimal(obj.opportunity.amount or 0)
        obj.original_value = source.quantize(Decimal("0.01"))
    elif obj.opportunity_id:
        obj.original_category = obj.opportunity.forecast_category
    return obj


def _attach_save_error(form, exc):
    """Route a model-level save refusal onto the right form field, or the form itself."""
    if isinstance(exc, ValidationError) and hasattr(exc, "error_dict"):
        for field_name, errors in exc.message_dict.items():
            for error in errors:
                form.add_error(
                    field_name if field_name in form.fields else None,
                    error,
                )
        return
    form.add_error(
        None, "That adjustment could not be saved. Check the call and the reason code.",
    )


@tenant_admin_required
def forecast_adjustment_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ForecastAdjustmentForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            submission = form.cleaned_data.get("submission")
            # "You cannot adjust a level above you" -- a business rule over a role check, not
            # a record ACL, so a tenant admin passes it. Refused here, server-side.
            if submission is not None and _adjusts_above_acting_level(request.user, submission):
                raise PermissionDenied("You cannot adjust a forecast call above your own level.")
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.tenant = request.tenant
                    obj.created_by = request.user
                    _snapshot_system_value(obj, submission)
                    obj.full_clean()
                    obj.save()
                    write_audit_log(
                        request.user, obj, "create",
                        {
                            "operation": "create_adjustment",
                            "reason_code": str(obj.reason_code)[:200],
                            "adjustment_kind": str(obj.adjustment_kind)[:200],
                        },
                        tenant=request.tenant,
                    )
            except (ValidationError, IntegrityError) as exc:
                _attach_save_error(form, exc)
                return render(request, TEMPLATE_FORM, _form_context(request, form, False))
            messages.success(request, "Adjustment recorded against the forecast call.")
            return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    else:
        form = ForecastAdjustmentForm(tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, False))


@tenant_admin_required
def forecast_adjustment_edit(request, pk):
    obj = get_object_or_404(_adjustment_queryset(request), pk=pk)
    if request.method == "POST":
        form = ForecastAdjustmentForm(
            request.POST, instance=obj, tenant=request.tenant, user=request.user,
        )
        if form.is_valid():
            # A reset row is closed history; re-editing it would rewrite a closed audit
            # entry. Refused here so the rule is server-side, not template-side.
            if obj.is_reverted:
                form.add_error(None, "A reverted adjustment is history and cannot be edited.")
                return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))
            try:
                with transaction.atomic():
                    updated = form.save(commit=False)
                    updated.tenant = request.tenant
                    updated.full_clean()
                    updated.save()
                    write_audit_log(
                        request.user, updated, "update",
                        {
                            "operation": "create_adjustment",
                            "reason_code": str(updated.reason_code)[:200],
                            "adjustment_kind": str(updated.adjustment_kind)[:200],
                        },
                        tenant=request.tenant,
                    )
            except (ValidationError, IntegrityError) as exc:
                _attach_save_error(form, exc)
                return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))
            messages.success(request, "Adjustment updated.")
            return redirect("sales:forecast_adjustment_detail", pk=updated.pk)
    else:
        form = ForecastAdjustmentForm(instance=obj, tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))


def _refuse_message(exc):
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)[:300] or "That adjustment cannot be changed."
    return "That adjustment could not be saved."


@require_POST
@tenant_admin_required
def forecast_adjustment_revert(request, pk):
    obj = get_object_or_404(_adjustment_queryset(request), pk=pk)
    form = ForecastRevertForm(request.POST or None, tenant=request.tenant)
    if not form.is_valid():
        messages.error(
            request,
            "; ".join(
                error for errors in form.errors.values() for error in errors
            )[:300] or "A Reset must say why.",
        )
        return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    if obj.is_reverted:
        messages.error(request, "That adjustment has already been reset.")
        return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    if obj.submission_id and obj.submission.period_id and obj.submission.period.is_locked:
        messages.error(request, "The period is locked, so its forecast calls are read-only.")
        return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    try:
        with transaction.atomic():
            locked = ForecastAdjustment.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            # Reset writes a flag, a timestamp and a mandatory reason. It never has to
            # recompute a "current" value, because the system value was never stored.
            locked.mark_reverted(request.user, form.cleaned_data["revert_reason"])
            locked.full_clean()
            locked.save()
            write_audit_log(
                request.user, locked, "update",
                {
                    "operation": "revert_adjustment",
                    "reason_code": str(locked.reason_code)[:200],
                    "revert_reason": str(locked.revert_reason)[:200],
                },
                tenant=request.tenant,
            )
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _refuse_message(exc))
        return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    messages.success(request, "Adjustment reset. The override no longer moves the forecast.")
    return redirect("sales:forecast_adjustment_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def forecast_adjustment_delete(request, pk):
    obj = get_object_or_404(_adjustment_queryset(request), pk=pk)
    # A reverted row is the closed half of the audit pair; deleting it would erase the reason
    # the override was undone, so it is refused server-side rather than hidden in the UI.
    if obj.is_reverted:
        messages.error(request, "A reverted adjustment is history and cannot be deleted.")
        return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    try:
        with transaction.atomic():
            locked = ForecastAdjustment.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            write_audit_log(
                request.user, locked, "delete",
                {
                    "action": "forecast_adjustment",
                    "adjustment": str(locked),
                    "reason_code": str(locked.reason_code)[:200],
                },
                tenant=request.tenant,
            )
            locked.delete()
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _refuse_message(exc))
        return redirect("sales:forecast_adjustment_detail", pk=obj.pk)
    messages.success(request, "Adjustment deleted.")
    return redirect("sales:forecast_adjustment_list")


@login_required
def forecast_adjustment_export(request):
    queryset, filters = _filter_adjustment_queryset(request, _adjustment_queryset(request))
    rows = (
        (
            obj.number,
            obj.submission.number,
            str(obj.submission.period) if obj.submission.period_id else "",
            obj.opportunity.name if obj.opportunity_id else "",
            obj.placement.pipeline.name if obj.placement_id else "",
            obj.get_adjustment_kind_display(),
            obj.get_target_field_display(),
            obj.original_value if obj.target_field == "amount" else (obj.original_category or ""),
            obj.adjusted_value if obj.target_field == "amount" else (obj.adjusted_category or ""),
            obj.net_delta if obj.net_delta is not None else "",
            obj.get_reason_code_display(),
            obj.note[:200] if obj.note else "",
            obj.created_by.get_full_name() if obj.created_by_id else "",
            "yes" if obj.is_reverted else "no",
            obj.revert_reason,
            obj.reverted_at or "",
        )
        for obj in queryset.order_by("-created_at", "-id")[:5000]
    )
    return csv_export_response(
        request,
        filename="sales-forecast-adjustments.csv",
        dataset="forecast_adjustments",
        headers=[
            "Number", "Forecast call", "Period", "Opportunity", "Pipeline", "Kind",
            "Target field", "System value", "Adjusted value", "Net delta", "Reason code",
            "Note", "Recorded by", "Reverted", "Revert reason", "Reverted at",
        ],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
