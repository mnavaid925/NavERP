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
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from apps.accounts.models import User
from apps.core.crud import apply_search, as_db_int, paginate
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity, SalesQuota, Territory
from apps.sales.forecast_services import (
    AI_GATE_MIN_PER_CLASS,
    _call_period,
    _open_opportunities,
    _rollup_by_currency,
    _undated_opportunity_count,
    forecast_ai_gate,
    forecast_submission_snapshot,
)
from apps.sales.forms.SalesForecasting.ForecastSubmissions import (
    ForecastReviewForm,
    ForecastSubmissionForm,
)
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline
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

# `forecast_submission_snapshot` (the three snapshot figures) and `forecast_ai_gate` (the
# 40-won AND 40-lost gate) now live in `apps/sales/forecast_services.py`, along with the
# private period-window/currency/opportunity helpers they share. They are services, not
# views, so they are not re-exported from `apps.sales.views`.


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


def _undated_pipeline_note(obj):
    """Caveat text when a call's pipeline includes deals with no expected close date.

    Empty string when every matched deal is dated, so the template renders nothing.
    """
    count = _undated_opportunity_count(
        obj.tenant_id, obj.owner, obj.territory, obj.pipeline, _call_period(obj),
    )
    if not count:
        return ""
    deals = "deal" if count == 1 else "deals"
    return (
        f"{count} of the {deals} behind this call have no expected close date. They are "
        "counted here as landing in the period, because an undated open deal is still "
        "live pipeline rather than no pipeline at all."
    )


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
        "undated_pipeline_note": _undated_pipeline_note(obj),
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
