"""8.4 Sales Forecasting — forecast period views.

Every queryset here is `tenant=request.tenant`-scoped; `request.tenant` is `None` for the
`admin` superuser, and an empty register is the correct answer for them (multi-tenancy
rule 1/2), never an `.all()`.

`ForecastSubmission` and `ForecastScenario` are built in later passes, so the detail view
resolves them through the app registry rather than importing them. Until they land the
period's own attributes, dates, flags and FX note still render -- only the dependent lists
are empty.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Currency
from apps.core.crud import apply_search, paginate
from apps.crm.models import Opportunity, SalesQuota
from apps.sales.forms.SalesForecasting.ForecastPeriods import ForecastPeriodForm
from apps.sales.models.SalesForecasting.ForecastPeriods import (
    ForecastPeriod,
    _optional_sales_model,
)
from apps.sales.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "sales/salesforecasting/forecastperiod/list.html"
TEMPLATE_DETAIL = "sales/salesforecasting/forecastperiod/detail.html"
TEMPLATE_FORM = "sales/salesforecasting/forecastperiod/form.html"

ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]
LOCKED_CHOICES = [("locked", "Locked"), ("unlocked", "Unlocked")]

#: A period is "current" when today falls inside its computed window. Mirrors the
#: `is_current` property, expressed as a queryset so the list can count it in one query.
#: Built per request, never at import time -- a module-level `localdate()` would freeze
#: "today" for the life of the process.
def _current_q():
    today = timezone.localdate()
    return Q(start_date__lte=today, end_date__gte=today)

#: The five `crm.Opportunity` forecast categories, each mapping to its
#: `ForecastSubmission` amount column. Reused verbatim -- 8.4 never re-spells the vocabulary.
CATEGORY_AMOUNT_FIELDS = [
    ("omitted", "omitted_amount"),
    ("pipeline", "pipeline_amount"),
    ("best_case", "best_case_amount"),
    ("commit", "commit_amount"),
    ("closed", "closed_amount"),
]
#: The four rollup buckets (everything but `omitted`, which is an explicit exclusion).
CURRENCY_ROLLUP_FIELDS = [
    ("pipeline", "pipeline_amount"),
    ("best_case", "best_case_amount"),
    ("commit", "commit_amount"),
    ("closed", "closed_amount"),
]


def _period_queryset(request):
    return ForecastPeriod.objects.filter(tenant=request.tenant).select_related("reporting_currency")


def _is_tenant_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _filter_period_queryset(request, queryset):
    """Parse GET and apply every filter BEFORE pagination (L11 on enum params)."""
    filters = {
        "q": request.GET.get("q", "").strip()[:200],
        "period_type": request.GET.get("period_type", ""),
        "rollup_dimension": request.GET.get("rollup_dimension", ""),
        "active": request.GET.get("active", ""),
        "locked": request.GET.get("locked", ""),
    }
    # A junk enum value is reset to "" so a stale bookmark shows the unfiltered register
    # rather than an empty one.
    if filters["period_type"] not in dict(SalesQuota.PERIOD_CHOICES):
        filters["period_type"] = ""
    if filters["rollup_dimension"] not in dict(ForecastPeriod.ROLLUP_DIMENSION_CHOICES):
        filters["rollup_dimension"] = ""
    if filters["active"] not in dict(ACTIVE_CHOICES):
        filters["active"] = ""
    if filters["locked"] not in dict(LOCKED_CHOICES):
        filters["locked"] = ""

    queryset = apply_search(queryset, filters["q"], ["name", "number"])
    if filters["period_type"]:
        queryset = queryset.filter(period_type=filters["period_type"])
    if filters["rollup_dimension"]:
        queryset = queryset.filter(rollup_dimension=filters["rollup_dimension"])
    if filters["active"] == "active":
        queryset = queryset.filter(is_active=True)
    elif filters["active"] == "inactive":
        queryset = queryset.filter(is_active=False)
    if filters["locked"] == "locked":
        queryset = queryset.filter(is_locked=True)
    elif filters["locked"] == "unlocked":
        queryset = queryset.filter(is_locked=False)
    return queryset, filters


@login_required
def forecast_period_list(request):
    queryset, filters = _filter_period_queryset(request, _period_queryset(request))
    page_obj = paginate(request, queryset, 20)
    base = _period_queryset(request)
    stats = base.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        inactive=Count("pk", filter=Q(is_active=False)),
        locked=Count("pk", filter=Q(is_locked=True)),
        current=Count("pk", filter=_current_q()),
    )
    export_url = reverse("sales:forecast_period_export")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, TEMPLATE_LIST, {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": filters["q"],
        "period_type": filters["period_type"],
        "rollup_dimension": filters["rollup_dimension"],
        "active": filters["active"],
        "locked": filters["locked"],
        "period_type_choices": SalesQuota.PERIOD_CHOICES,
        "rollup_dimension_choices": ForecastPeriod.ROLLUP_DIMENSION_CHOICES,
        "active_choices": ACTIVE_CHOICES,
        "locked_choices": LOCKED_CHOICES,
        "stats": stats,
        "export_url": export_url,
        "can_edit_all": _is_tenant_admin(request.user),
    })


def _period_rollups(obj, submissions):
    """Category totals, the currency-bucketed rollup and the count by status.

    Amounts are summed as ``Decimal`` and grouped by **currency code only** -- a bucket is
    never combined with another and a missing currency stays an explicit ``unspecified``
    bucket rather than silently defaulting to USD (L29).
    """
    category_totals = {value: Decimal("0") for value, _ in CATEGORY_AMOUNT_FIELDS}
    for submission in submissions:
        for value, field in CATEGORY_AMOUNT_FIELDS:
            category_totals[value] += Decimal(getattr(submission, field, 0) or 0)

    submission_rows = []
    submission_model = _optional_sales_model("ForecastSubmission")
    if submission_model is not None:
        labels = dict(submission_model.STATUS_CHOICES)
        for row in (
            submission_model.objects.filter(period=obj, tenant_id=obj.tenant_id)
            .values("status")
            .annotate(count=Count("pk"))
            .order_by("status")
        ):
            submission_rows.append({
                "status": row["status"],
                "label": labels.get(row["status"], row["status"]),
                "count": row["count"],
            })

    # The reporting currency is a property of the period, so there is exactly one bucket.
    code = obj.reporting_currency.code if obj.reporting_currency_id else "unspecified"
    bucket = {key: Decimal("0") for key, _ in CURRENCY_ROLLUP_FIELDS}
    for submission in submissions:
        for key, field in CURRENCY_ROLLUP_FIELDS:
            bucket[key] += Decimal(getattr(submission, field, 0) or 0)
    bucket["total"] = sum(bucket.values(), Decimal("0"))
    currency_rollups = {code: bucket}
    return category_totals, currency_rollups, submission_rows


def _fx_note(obj):
    """The FX provenance sentence: which rate date applies, or that none was set."""
    if not obj.reporting_currency_id:
        return "No reporting currency is set, so no exchange rate is applied to this period."
    if obj.fx_rate_source_date:
        return (
            f"Rates are read from the exchange-rate table at {obj.fx_rate_source_date:%b %d, %Y}. "
            "A missing rate is reported as a caveat and is never defaulted to 1.0."
        )
    return (
        "No FX source date is set, so the period's end date is used to look up a rate. "
        "A missing rate is reported as a caveat and is never defaulted to 1.0."
    )


@login_required
def forecast_period_detail(request, pk):
    obj = get_object_or_404(_period_queryset(request), pk=pk)
    submission_model = _optional_sales_model("ForecastSubmission")
    scenario_model = _optional_sales_model("ForecastScenario")
    if submission_model is not None:
        submissions = list(
            submission_model.objects.filter(period=obj, tenant_id=obj.tenant_id)
            .select_related("owner", "org_unit", "territory")
            .order_by("-created_at", "-id")[:200]
        )
        submissions_count = submission_model.objects.filter(
            period=obj, tenant_id=obj.tenant_id,
        ).count()
    else:
        submissions = []
        submissions_count = 0
    scenarios = []
    if scenario_model is not None:
        scenarios = list(
            scenario_model.objects.filter(period=obj, tenant_id=obj.tenant_id)
            .order_by("-created_at", "-id")[:200]
        )
    category_totals, currency_rollups, submission_rows = _period_rollups(obj, submissions)
    # total_forecast_amount is the sum over the category dict -- a derived figure, never a
    # stored column.
    total_forecast_amount = sum(category_totals.values(), Decimal("0"))
    can_edit = _is_tenant_admin(request.user)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "submissions": submissions,
        "submissions_count": submissions_count,
        "submission_rows": submission_rows,
        "status_choices": (
            list(submission_model.STATUS_CHOICES) if submission_model is not None else []
        ),
        "category_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
        "scenarios": scenarios,
        "category_totals": category_totals,
        "total_forecast_amount": total_forecast_amount,
        "currency_rollups": currency_rollups,
        "fx_note": _fx_note(obj),
        "can_edit": can_edit,
        "can_lock": can_edit,
        "is_locked": obj.is_locked,
    })


#: The fields a locked period's shape is frozen on (contract 4.1).
SHAPE_FIELDS = ("name", "period_type", "period_year", "period_number", "rollup_dimension")


def _shape_unchanged(locked_period, form):
    """True when a POST leaves every frozen shape field exactly as stored."""
    return all(
        form.cleaned_data.get(name) == getattr(locked_period, name)
        for name in SHAPE_FIELDS
    )


def _form_context(request, form, is_edit, obj=None):
    return {
        "form": form,
        "is_edit": is_edit,
        "obj": obj,
        "period_type_choices": SalesQuota.PERIOD_CHOICES,
        "rollup_dimension_choices": ForecastPeriod.ROLLUP_DIMENSION_CHOICES,
        # Currency is global: active rows only, never tenant-filtered (L29).
        "currencies": list(Currency.objects.filter(is_active=True).order_by("code")[:500]),
        "can_lock": _is_tenant_admin(request.user),
        "is_locked": bool(obj.is_locked) if obj is not None else False,
    }


@tenant_admin_required
def forecast_period_create(request):
    if request.method == "POST":
        form = ForecastPeriodForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.tenant = request.tenant
                    obj.save()
            except IntegrityError:
                # Two admins submitting the same (type, year, number) at once: the composite
                # unique wins, and the loser is told which period already owns it.
                existing = ForecastPeriod.objects.filter(
                    tenant=request.tenant,
                    period_type=form.cleaned_data.get("period_type"),
                    period_year=form.cleaned_data.get("period_year"),
                    period_number=form.cleaned_data.get("period_number"),
                ).first()
                if existing is None:
                    raise
                form.add_error(None, "That period already exists for this workspace.")
                return render(request, TEMPLATE_FORM, _form_context(request, form, False))
            write_audit_log(
                request.user, obj, "create",
                {"action": "forecast_period", "period": str(obj)},
                tenant=request.tenant,
            )
            messages.success(request, "Forecast period created.")
            return redirect("sales:forecast_period_detail", pk=obj.pk)
    else:
        form = ForecastPeriodForm(tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, False))


@tenant_admin_required
def forecast_period_edit(request, pk):
    obj = get_object_or_404(_period_queryset(request), pk=pk)
    if request.method == "POST":
        # R9: the lock is enforced SERVER-side, not merely hidden in the template. The form
        # marks name / period_type / period_year / period_number / rollup_dimension
        # `disabled`, and Django ignores POST data for a disabled field -- so a crafted POST
        # cannot reshape a locked period. Only is_active / fx_rate_source_date /
        # reporting_currency may still move, which is exactly what 4.1 allows.
        form = ForecastPeriodForm(
            request.POST, instance=obj, tenant=request.tenant, user=request.user,
        )
        if form.is_valid():
            with transaction.atomic():
                locked = ForecastPeriod.objects.select_for_update().get(
                    pk=obj.pk, tenant=request.tenant,
                )
                # Re-read inside the lock: a concurrent POST may have locked the period
                # between the form bound and this write.
                if locked.is_locked and not _shape_unchanged(locked, form):
                    form.add_error(None, "A locked period's shape cannot be changed.")
                if not form.errors:
                    form.instance = locked
                    for field_name in form._meta.fields:
                        model_field = form.instance._meta.get_field(field_name)
                        if (
                            model_field.concrete
                            and not model_field.many_to_many
                            and field_name in form.cleaned_data
                        ):
                            setattr(form.instance, field_name, form.cleaned_data[field_name])
                    obj = form.save(commit=False)
                    obj.tenant = request.tenant
                    obj.save()
            if form.errors:
                return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))
            write_audit_log(
                request.user, obj, "update",
                {"action": "forecast_period", "period": str(obj)},
                tenant=request.tenant,
            )
            messages.success(request, "Forecast period updated.")
            return redirect("sales:forecast_period_detail", pk=obj.pk)
    else:
        form = ForecastPeriodForm(instance=obj, tenant=request.tenant, user=request.user)
    return render(request, TEMPLATE_FORM, _form_context(request, form, True, obj))


def _set_lock_state(request, pk, locked_state):
    obj = get_object_or_404(_period_queryset(request), pk=pk)
    if obj.is_locked == locked_state:
        messages.info(
            request,
            "This forecast period is already locked." if locked_state
            else "This forecast period is already unlocked.",
        )
        return redirect("sales:forecast_period_detail", pk=obj.pk)
    with transaction.atomic():
        locked = ForecastPeriod.objects.select_for_update().get(
            pk=obj.pk, tenant=request.tenant,
        )
        locked.is_locked = locked_state
        locked.save(update_fields=["is_locked", "updated_at"])
    write_audit_log(
        request.user, locked, "update",
        {"operation": "lock_period" if locked_state else "unlock_period", "period": str(locked)},
        tenant=request.tenant,
    )
    messages.success(
        request,
        "Forecast period locked. Its submissions are now read-only."
        if locked_state else "Forecast period unlocked.",
    )
    return redirect("sales:forecast_period_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def forecast_period_lock(request, pk):
    return _set_lock_state(request, pk, True)


@require_POST
@tenant_admin_required
def forecast_period_unlock(request, pk):
    return _set_lock_state(request, pk, False)


@require_POST
@tenant_admin_required
def forecast_period_delete(request, pk):
    obj = get_object_or_404(_period_queryset(request), pk=pk)
    # R8: ForecastSubmission.period / ForecastScenario.period are PROTECT, and
    # ForecastPeriod.delete() additionally refuses while either child exists. Both raise
    # before any row is removed, so catching here turns a 500 into a message.
    try:
        with transaction.atomic():
            locked = ForecastPeriod.objects.select_for_update().get(
                pk=obj.pk, tenant=request.tenant,
            )
            write_audit_log(
                request.user, locked, "delete",
                {"action": "forecast_period", "period": str(locked)},
                tenant=request.tenant,
            )
            locked.delete()
    except (ValidationError, ProtectedError, IntegrityError) as exc:
        messages.error(request, _delete_refusal(exc))
        return redirect("sales:forecast_period_detail", pk=obj.pk)
    messages.success(request, "Forecast period deleted.")
    return redirect("sales:forecast_period_list")


def _delete_refusal(exc):
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages) or "This forecast period cannot be deleted."
    return "This forecast period is referenced by forecast records and cannot be deleted."


@login_required
def forecast_period_export(request):
    queryset, filters = _filter_period_queryset(request, _period_queryset(request))
    rows = (
        (
            obj.number,
            obj.name,
            obj.label,
            obj.get_period_type_display(),
            obj.period_year,
            obj.period_number,
            obj.get_rollup_dimension_display(),
            obj.reporting_currency.code if obj.reporting_currency_id else "",
            obj.fx_rate_source_date or "",
            obj.start_date,
            obj.end_date,
            "Yes" if obj.is_active else "No",
            "Yes" if obj.is_locked else "No",
        )
        for obj in queryset.order_by("-period_year", "period_number", "name")[:5000]
    )
    return csv_export_response(
        request,
        filename="sales-forecast-periods.csv",
        dataset="forecast_periods",
        headers=[
            "Number", "Name", "Label", "Period type", "Year", "Period number",
            "Rollup dimension", "Reporting currency", "FX rate source date",
            "Start date", "End date", "Active", "Locked",
        ],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
