"""8.4 Sales Forecasting — forecast submission views.

Every queryset is `tenant=request.tenant`-scoped; `request.tenant` is `None` for the
`admin` superuser and an empty register is the correct answer for them (multi-tenancy
rule 1/2), never an `.all()`.

The three service-written snapshots are refreshed on the submit path, not on every read:
`weighted_amount` from `sales.OpportunityPipelinePlacement.effective_probability`,
`quota_amount` from `crm.SalesQuota.target_amount` by value, and `actual_amount` from
append-only `sales.OpportunityOutcome` rows with `result="won"` inside the period window.
`total_forecast_amount` / `variance_amount` / `attainment_pct` / `pace_pct` are properties
on the model and are never written here.

The AI block is storage + explanation only. Nothing is predicted and nothing is rendered
below the 40-won-AND-40-lost gate counted from `sales.OpportunityOutcome`.
"""
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from apps.accounts.models import User
from apps.core.crud import apply_search, as_db_int, paginate
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity, SalesQuota, Territory
from apps.sales.forms.SalesForecasting.ForecastSubmissions import (
    ForecastReviewForm,
    ForecastSubmissionForm,
)
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome
from apps.sales.models.OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacement,
    Pipeline,
)
from apps.sales.models.SalesForecasting.ForecastPeriods import (
    ForecastPeriod,
    _optional_sales_model,
)
from apps.sales.models.SalesForecasting.ForecastSubmissions import (
    CATEGORY_AMOUNT_FIELDS,
    ForecastSubmission,
)
from apps.sales.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "sales/salesforecasting/forecastsubmission/list.html"
TEMPLATE_DETAIL = "sales/salesforecasting/forecastsubmission/detail.html"
TEMPLATE_FORM = "sales/salesforecasting/forecastsubmission/form.html"

#: The AI eligibility gate (contract 0.5): BOTH sides must clear it, counted from the
#: append-only outcome table. Below it, no prediction value is ever rendered.
AI_GATE_MIN_PER_CLASS = 40


def _is_tenant_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _submission_queryset(request):
    return ForecastSubmission.objects.filter(tenant=request.tenant).select_related(
        "period", "owner", "org_unit", "territory", "pipeline", "quota_ref",
    )


def _filter_submission_queryset(request, queryset):
    """Parse GET and apply every filter BEFORE pagination (L11 on both param kinds)."""
    filters = {
        "q": request.GET.get("q", "").strip()[:200],
        "status": request.GET.get("status", "").strip(),
        "period_id": as_db_int(request.GET.get("period_id", "")),
        "owner_id": as_db_int(request.GET.get("owner_id", "")),
        "org_unit_id": as_db_int(request.GET.get("org_unit_id", "")),
        "territory_id": as_db_int(request.GET.get("territory_id", "")),
        "pipeline_id": as_db_int(request.GET.get("pipeline_id", "")),
    }
    # A junk enum resets to "" so a stale bookmark shows the unfiltered register rather
    # than an empty one.
    if filters["status"] not in dict(ForecastSubmission.STATUS_CHOICES):
        filters["status"] = ""
    queryset = apply_search(queryset, filters["q"], ["number", "notes", "review_note"])
    if filters["status"]:
        queryset = queryset.filter(status=filters["status"])
    # Integer FK params go through as_db_int, so ?period=abc and an over-range
    # ?period=999...9 are SKIPPED rather than 500 (L11).
    for param, lookup in (
        ("period_id", "period_id"),
        ("owner_id", "owner_id"),
        ("org_unit_id", "org_unit_id"),
        ("territory_id", "territory_id"),
        ("pipeline_id", "pipeline_id"),
    ):
        number = filters[param]
        if number is not None and number != 0:
            queryset = queryset.filter(**{lookup: number})
    return queryset, filters


def _filter_choices(tenant):
    """The bounded FK lists the list and form filter dropdowns read.

    Owners come back as ``{"pk", "label"}`` dicts rather than raw ``User`` rows: a bounded
    dropdown only needs an id and a name, and shipping 500 hydrated users into a page whose
    template only prints two fields of each is the page-weight bug the bound exists to stop.
    """
    if tenant is None:
        return [], [], [], []
    periods = list(
        ForecastPeriod.objects.filter(tenant=tenant)
        .order_by("-period_year", "period_number", "name")[:200]
    )
    owners = [
        {"pk": pk, "label": (f"{first_name} {last_name}".strip() or username)}
        for pk, username, first_name, last_name in User.objects.filter(
            tenant=tenant, is_active=True,
        ).order_by("username").values_list("pk", "username", "first_name", "last_name")[:500]
    ]
    org_units = list(OrgUnit.objects.filter(tenant=tenant).order_by("name")[:500])
    territories = list(
        Territory.objects.filter(tenant=tenant, is_active=True).order_by("name")[:500]
    )
    return periods, owners, org_units, territories


def _pipelines(tenant):
    if tenant is None:
        return []
    return list(
        Pipeline.objects.filter(tenant=tenant, is_active=True).order_by("name")[:500]
    )


def _quotas(tenant):
    """``crm.SalesQuota`` is read-only to 8.4 (quota design is 8.7's) — snapshot by value."""
    if tenant is None:
        return []
    return list(
        SalesQuota.objects.filter(tenant=tenant)
        .order_by("-period_year", "period_number")[:500]
    )


def _period_window(period):
    """``(start_date, end_date)`` for a period, or ``None`` when undated.

    Dates, not datetimes: ``closed_at`` is matched with ``__date__range`` so the window is
    evaluated in the database's own date semantics on both MySQL and SQLite, and a
    timezone offset can never push a boundary close out of the period.
    """
    if not period or not period.start_date or not period.end_date:
        return None
    return period.start_date, period.end_date


def _reporting_currency_id(period):
    """The currency a call's scalar amounts are stated in — the period's, or none."""
    if period is None or not period.reporting_currency_id:
        return None
    return period.reporting_currency_id


def _open_opportunities(tenant, owner, territory, pipeline, period):
    """The open opportunities behind this call, inside the period window.

    ``closed_lost`` is excluded: a lost deal is not forecastable. No currency filter is
    applied here — the caller decides, because the scalar snapshot and the per-currency
    breakdown want different things from the same base.
    """
    queryset = Opportunity.objects.filter(tenant=tenant)
    if owner is not None:
        queryset = queryset.filter(owner=owner)
    if territory is not None:
        queryset = queryset.filter(territory=territory)
    if pipeline is not None:
        queryset = queryset.filter(
            pk__in=OpportunityPipelinePlacement.objects.filter(
                pipeline=pipeline, tenant=tenant,
            ).values_list("opportunity_id", flat=True)
        )
    window = _period_window(period)
    if window is not None:
        queryset = queryset.filter(close_date__gte=window[0], close_date__lte=window[1])
    return queryset.exclude(stage="closed_lost")


def _rollup_by_currency(opportunities):
    """``{currency_code: {"weighted": Decimal, "open": int}}`` in ONE pass.

    Each verified currency keeps its own bucket and a missing currency lands in an explicit
    ``unspecified`` rather than defaulting to USD; the codes are never added together.
    Weighting uses ``OpportunityPipelinePlacement.effective_probability`` — the property
    that already prefers ``probability_override`` over the stage probability — and falls
    back to the opportunity's own probability when the deal is not on a pipeline.
    """
    rollups = {}
    for opportunity in opportunities.select_related(
        "currency", "sales_pipeline_placement", "sales_pipeline_placement__current_stage",
    ):
        placement = getattr(opportunity, "sales_pipeline_placement", None)
        probability = (
            placement.effective_probability if placement is not None
            else opportunity.probability
        )
        code = opportunity.currency.code if opportunity.currency_id else "unspecified"
        bucket = rollups.setdefault(code, {"weighted": Decimal("0"), "open": 0})
        bucket["weighted"] += Decimal(opportunity.amount or 0) * Decimal(probability) / Decimal("100")
        bucket["open"] += 1
    for bucket in rollups.values():
        bucket["weighted"] = bucket["weighted"].quantize(Decimal("0.01"))
    return rollups


def forecast_submission_snapshot(submission, tenant=None):
    """The three service-written snapshot figures for one call, as plain ``Decimal``.

    The scalar ``weighted_amount`` and ``actual_amount`` are counted in the period's
    **reporting currency only**, so a single stored figure is never a sum over unlike
    amounts (L29). A period with no reporting currency adopts the call's own single
    currency and reports zero when the call genuinely spans several — the per-currency
    breakdown on the detail page is where those are still visible.

    ``quota_amount`` is frozen by value from ``crm.SalesQuota.target_amount``, so a later
    quota edit never rewrites this call. ``actual_amount`` reads the append-only
    ``sales.OpportunityOutcome`` table for wins closed inside the period window.
    """
    tenant = tenant or submission.tenant
    period = _call_period(submission)
    currency_id = _reporting_currency_id(period)
    reporting_code = period.reporting_currency.code if currency_id is not None else None
    rollups = _rollup_by_currency(_open_opportunities(
        tenant, submission.owner, submission.territory, submission.pipeline, period,
    ))
    if reporting_code is not None:
        weighted = rollups.get(reporting_code, {}).get("weighted", Decimal("0"))
    elif len(rollups) == 1:
        weighted = next(iter(rollups.values()))["weighted"]
    else:
        weighted = Decimal("0")
    quota = (
        Decimal(submission.quota_ref.target_amount or 0)
        if submission.quota_ref_id else Decimal("0")
    )
    actual = Decimal("0")
    window = _period_window(period)
    if window is not None:
        won = OpportunityOutcome.objects.filter(
            tenant=tenant, result="won", closed_at__date__range=window,
        )
        if submission.owner_id:
            won = won.filter(opportunity__owner_id=submission.owner_id)
        if submission.territory_id:
            won = won.filter(opportunity__territory_id=submission.territory_id)
        if currency_id is not None:
            won = won.filter(opportunity__currency_id=currency_id)
        actual = Decimal(won.aggregate(total=Sum("opportunity__amount"))["total"] or 0)
    return {
        "weighted_amount": weighted.quantize(Decimal("0.01")),
        "quota_amount": quota.quantize(Decimal("0.01")),
        "actual_amount": actual.quantize(Decimal("0.01")),
        "currency_codes": sorted(rollups),
    }


def _call_period(submission):
    """The call's period, or ``None`` when it has no computed window to scope by."""
    if not submission.period_id:
        return None
    period = submission.period
    return period if (period.start_date and period.end_date) else None


def forecast_ai_gate(tenant):
    """``(available, message)`` for the AI block — the 40-won AND 40-lost gate."""
    if tenant is None:
        return False, "Select a tenant workspace to see a prediction."
    counts = {
        row["result"]: row["total"]
        for row in OpportunityOutcome.objects.filter(tenant=tenant)
        .values("result")
        .annotate(total=Count("pk"))
    }
    won = counts.get("won", 0)
    lost = counts.get("lost", 0)
    if won >= AI_GATE_MIN_PER_CLASS and lost >= AI_GATE_MIN_PER_CLASS:
        return True, ""
    return False, (
        f"A prediction needs at least {AI_GATE_MIN_PER_CLASS} won and "
        f"{AI_GATE_MIN_PER_CLASS} lost recorded opportunities. This workspace has "
        f"{won} won and {lost} lost."
    )


@login_required
def forecast_submission_list(request):
    base = _submission_queryset(request)
    queryset, filters = _filter_submission_queryset(request, base)
    page_obj = paginate(request, queryset, 20)
    periods, owners, org_units, territories = _filter_choices(request.tenant)
    pipelines = _pipelines(request.tenant)
    stats = base.aggregate(
        total=Count("pk"),
        draft=Count("pk", filter=Q(status="draft")),
        submitted=Count("pk", filter=Q(status="submitted")),
        approved=Count("pk", filter=Q(status="approved")),
        rejected=Count("pk", filter=Q(status="rejected")),
        locked=Count("pk", filter=Q(status="locked")),
    )
    # The page total is a PROPERTY sum over the page, and it is deliberately NOT called
    # `total_forecast_amount` here: on a list that name reads as a single object's figure
    # and the template would silently pick up the wrong one (contract 6.2 / 13.7).
    page_total_forecast = sum(
        (obj.total_forecast_amount for obj in page_obj.object_list), Decimal("0")
    )
    export_url = reverse("sales:forecast_submission_export")
    if request.GET.urlencode():
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, TEMPLATE_LIST, {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": filters["q"],
        "status": filters["status"],
        "period_id": filters["period_id"] or "",
        "owner_id": filters["owner_id"] or "",
        "org_unit_id": filters["org_unit_id"] or "",
        "territory_id": filters["territory_id"] or "",
        "pipeline_id": filters["pipeline_id"] or "",
        "status_choices": ForecastSubmission.STATUS_CHOICES,
        "periods": periods,
        "period_choices": [(p.pk, str(p)) for p in periods],
        "owners": owners,
        "org_units": org_units,
        "territories": territories,
        "pipelines": pipelines,
        "page_total_forecast": page_total_forecast,
        "stats": stats,
        "export_url": export_url,
        "can_edit_all": _is_tenant_admin(request.user),
    })


def _opportunity_rollups(obj):
    """Per-currency weighted amount and open count behind this call.

    Unlike the scalar ``weighted_amount`` snapshot, this deliberately does NOT narrow to
    the reporting currency: showing the other buckets is the whole point of the panel, and
    the codes are never added together here either.
    """
    return _rollup_by_currency(_open_opportunities(
        obj.tenant_id, obj.owner, obj.territory, obj.pipeline, _call_period(obj),
    ))


def _allowed_actions(obj, request):
    """The actions the acting user may take, re-derived server-side.

    ``allowed_actions`` on the model is the workflow state; this narrows it further by WHO
    is asking, so a rep is never offered a review or delete button they would be refused on,
    and a manager can never submit someone else's call as their own.
    """
    actions = list(obj.allowed_actions)
    is_admin = _is_tenant_admin(request.user)
    owns = obj.owner_id == request.user.pk
    if not is_admin:
        if not owns:
            actions = [action for action in actions if action not in {"edit", "submit"}]
        actions = [action for action in actions if action not in {"approve", "reject", "delete"}]
    return actions


@login_required
def forecast_submission_detail(request, pk):
    obj = get_object_or_404(_submission_queryset(request), pk=pk)
    category_amounts = {
        value: Decimal(getattr(obj, field, 0) or 0) for value, field in CATEGORY_AMOUNT_FIELDS
    }
    adjustment_model = _optional_sales_model("ForecastAdjustment")
    adjustment_rows = []
    if adjustment_model is not None:
        reason_labels = dict(getattr(adjustment_model, "REASON_CODE_CHOICES", []))
        for row in (
            adjustment_model.objects.filter(submission=obj, tenant_id=obj.tenant_id)
            .values("reason_code")
            .annotate(count=Count("pk"))
            .order_by("-count", "reason_code")
        ):
            adjustment_rows.append({
                "reason_code": row["reason_code"],
                "label": reason_labels.get(row["reason_code"], row["reason_code"] or "—"),
                "count": row["count"],
            })
    ai_available, ai_gate_message = forecast_ai_gate(request.tenant)
    allowed_actions = _allowed_actions(obj, request)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "period": obj.period if obj.period_id else None,
        "owner": obj.owner,
        "org_unit": obj.org_unit,
        "territory": obj.territory,
        "pipeline": obj.pipeline,
        "quota": obj.quota_ref if obj.quota_ref_id else None,
        "category_amounts": category_amounts,
        "total_forecast_amount": obj.total_forecast_amount,
        "weighted_amount": obj.weighted_amount,
        "quota_amount": obj.quota_amount,
        "actual_amount": obj.actual_amount,
        "variance_amount": obj.variance_amount,
        "attainment_pct": obj.attainment_pct,
        "pace_pct": obj.pace_pct,
        "adjustments": obj.adjustment_rows(),
        "adjustment_rows": adjustment_rows,
        "opportunity_rollups": _opportunity_rollups(obj),
        "ai_available": ai_available,
        "ai_gate_message": ai_gate_message,
        "ai_explanation": obj.ai_explanation,
        "status_choices": ForecastSubmission.STATUS_CHOICES,
        "allowed_actions": allowed_actions,
        "can_edit": "edit" in allowed_actions,
        "can_submit": "submit" in allowed_actions,
        "can_review": "approve" in allowed_actions or "reject" in allowed_actions,
        "is_period_locked": bool(obj.period_id and obj.period.is_locked),
    })


def _form_context(request, form, is_edit, obj=None):
    periods, owners, org_units, territories = _filter_choices(request.tenant)
    return {
        "form": form,
        "is_edit": is_edit,
        "obj": obj,
        "periods": periods,
        "owners": owners,
        "org_units": org_units,
        "territories": territories,
        "pipelines": _pipelines(request.tenant),
        "quotas": _quotas(request.tenant),
        # The five category amounts reuse the opportunity forecast vocabulary as their
        # field legend, so the form never re-spells it (contract 6.2).
        "category_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
        "is_period_locked": bool(
            obj.period.is_locked if (obj is not None and obj.period_id) else False
        ),
        "can_submit": bool(obj is None or "submit" in obj.allowed_actions),
    }


@login_required
def forecast_submission_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ForecastSubmissionForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.tenant = request.tenant
                    obj.full_clean(exclude=["submitted_by", "reviewed_by"])
                    obj.save()
            except (ValidationError, IntegrityError) as exc:
                # Two reps submitting the same (period, owner) call at once: the clean()
                # rule fires for the loser, and the (tenant, number) unique covers the mint.
                _attach_save_error(form, exc)
                return render(request, TEMPLATE_FORM, _form_context(request, form, False))
            write_audit_log(
                request.user, obj, "create",
                {"action": "forecast_submission", "submission": str(obj)},
                tenant=request.tenant,
            )
            messages.success(request, "Forecast call created.")
            return redirect("sales:forecast_submission_detail", pk=obj.pk)
    else:
        form = ForecastSubmissionForm(tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, False))


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
    form.add_error(None, "That forecast call could not be saved. Check the period and owner.")


@login_required
def forecast_submission_edit(request, pk):
    obj = get_object_or_404(_submission_queryset(request), pk=pk)
    if request.method == "POST":
        form = ForecastSubmissionForm(
            request.POST, instance=obj, tenant=request.tenant, user=request.user,
        )
        if form.is_valid():
            # A locked period, a frozen status and a tampered POST are all refused in
            # form.clean(), and re-checked here so the rule is server-side, not template-side.
            if obj.is_frozen or "edit" not in _allowed_actions(obj, request):
                form.add_error(None, "This forecast call is read-only.")
                return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))
            try:
                with transaction.atomic():
                    updated = form.save(commit=False)
                    updated.tenant = request.tenant
                    updated.full_clean(exclude=["submitted_by", "reviewed_by"])
                    updated.save()
            except (ValidationError, IntegrityError) as exc:
                _attach_save_error(form, exc)
                return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))
            write_audit_log(
                request.user, updated, "update",
                {"action": "edit_forecast_submission", "submission": str(updated)},
                tenant=request.tenant,
            )
            messages.success(request, "Forecast call updated.")
            return redirect("sales:forecast_submission_detail", pk=updated.pk)
    else:
        form = ForecastSubmissionForm(
            instance=obj, tenant=request.tenant, user=request.user,
        )
    return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))


@require_POST
@login_required
def forecast_submission_submit(request, pk):
    obj = get_object_or_404(_submission_queryset(request), pk=pk)
    # A locked period is read-only server-side; a rep may only submit their OWN call, unless
    # they are a tenant admin (contract 5.2).
    if obj.period_id and obj.period.is_locked:
        messages.error(request, "This period is locked, so its forecast calls are read-only.")
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    if obj.owner_id != request.user.pk and not _is_tenant_admin(request.user):
        messages.error(request, "You can only submit your own forecast call.")
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    if "submit" not in obj.allowed_actions:
        messages.error(
            request,
            f"A {obj.get_status_display().lower()} forecast call cannot be submitted.",
        )
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    try:
        with transaction.atomic():
            locked = ForecastSubmission.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            # The three snapshots are refreshed HERE, at submit time — not on every read — so
            # the numbers a reviewer approves are the numbers that were true at submission.
            snapshot = forecast_submission_snapshot(locked, tenant=request.tenant)
            locked.weighted_amount = snapshot["weighted_amount"]
            locked.quota_amount = snapshot["quota_amount"]
            locked.actual_amount = snapshot["actual_amount"]
            locked.mark_submitted(request.user)
            locked.full_clean(exclude=["submitted_by", "reviewed_by"])
            locked.save()
            write_audit_log(
                request.user, locked, "update",
                {
                    "operation": "submit_forecast",
                    "status": "submitted",
                    "total_forecast_amount": str(locked.total_forecast_amount)[:200],
                    "weighted_amount": str(locked.weighted_amount)[:200],
                },
                tenant=request.tenant,
            )
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _transition_message(exc))
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    messages.success(request, "Forecast call submitted for review.")
    return redirect("sales:forecast_submission_detail", pk=obj.pk)


def _transition_message(exc):
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)[:300] or "That transition is not allowed."
    return "That transition could not be saved."


@require_POST
@tenant_admin_required
def forecast_submission_approve(request, pk):
    return _review(request, pk, approved=True)


@require_POST
@tenant_admin_required
def forecast_submission_reject(request, pk):
    return _review(request, pk, approved=False)


def _review(request, pk, approved):
    obj = get_object_or_404(_submission_queryset(request), pk=pk)
    form = ForecastReviewForm(
        request.POST or None, tenant=request.tenant, approved=approved,
    )
    if not form.is_valid():
        for error in form.errors.get("note", []) or form.non_field_errors():
            messages.error(request, error)
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    note = (form.cleaned_data.get("note") or "").strip()[:200]
    if "approve" not in obj.allowed_actions and "reject" not in obj.allowed_actions:
        messages.error(
            request,
            f"A {obj.get_status_display().lower()} forecast call cannot be reviewed.",
        )
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    try:
        with transaction.atomic():
            locked = ForecastSubmission.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            locked.mark_reviewed(request.user, approved, note)
            locked.full_clean(exclude=["submitted_by", "reviewed_by"])
            locked.save()
            write_audit_log(
                request.user, locked, "update",
                {
                    "operation": "approve_forecast" if approved else "reject_forecast",
                    "note": note[:200],
                },
                tenant=request.tenant,
            )
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _transition_message(exc))
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    messages.success(
        request,
        "Forecast call approved." if approved else "Forecast call sent back to the rep.",
    )
    return redirect("sales:forecast_submission_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def forecast_submission_delete(request, pk):
    obj = get_object_or_404(_submission_queryset(request), pk=pk)
    # ForecastAdjustment.submission is PROTECT, so a call carrying manager overrides raises
    # ProtectedError before any row is removed. Catching here turns a 500 into a message.
    try:
        with transaction.atomic():
            locked = ForecastSubmission.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            write_audit_log(
                request.user, locked, "delete",
                {"action": "forecast_submission", "submission": str(locked)},
                tenant=request.tenant,
            )
            locked.delete()
    except (ValidationError, ProtectedError, IntegrityError) as exc:
        if isinstance(exc, ValidationError):
            reason = "; ".join(exc.messages) or "This forecast call cannot be deleted."
        else:
            reason = "This forecast call carries manager overrides and cannot be deleted."
        messages.error(request, reason)
        return redirect("sales:forecast_submission_detail", pk=obj.pk)
    messages.success(request, "Forecast call deleted.")
    return redirect("sales:forecast_submission_list")


@login_required
def forecast_submission_export(request):
    queryset, filters = _filter_submission_queryset(request, _submission_queryset(request))
    rows = (
        (
            obj.number,
            str(obj.period) if obj.period_id else "",
            obj.owner.get_full_name() if obj.owner_id else "",
            obj.org_unit.name if obj.org_unit_id else "",
            obj.territory.name if obj.territory_id else "",
            obj.pipeline.name if obj.pipeline_id else "",
            obj.get_status_display(),
            obj.omitted_amount,
            obj.pipeline_amount,
            obj.best_case_amount,
            obj.commit_amount,
            obj.closed_amount,
            obj.total_forecast_amount,
            obj.weighted_amount,
            obj.quota_amount,
            obj.actual_amount,
            obj.variance_amount,
            obj.submitted_at or "",
            obj.reviewed_at or "",
        )
        for obj in queryset.order_by("-created_at", "-id")[:5000]
    )
    return csv_export_response(
        request,
        filename="sales-forecast-submissions.csv",
        dataset="forecast_submissions",
        headers=[
            "Number", "Period", "Owner", "Org unit", "Territory", "Pipeline", "Status",
            "Omitted", "Pipeline amount", "Best case", "Commit", "Closed",
            "Total forecast", "Weighted", "Quota", "Actual", "Variance",
            "Submitted at", "Reviewed at",
        ],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
