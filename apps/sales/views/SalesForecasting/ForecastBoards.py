"""8.4 Sales Forecasting — the four derived report views.

`forecast_board`, `forecast_attainment`, `forecast_accuracy` and `forecast_call`
are **read-only reports over the four forecasting models** — this module adds no
model and needs no migration. Every figure is derived per request from
`ForecastPeriod` / `ForecastSubmission` / `ForecastAdjustment` /
`ForecastScenario`, never read off a stored total (the core spine rule: derived
values are computed, not editable columns).

Two rules dominate this file:

* **Multi-tenancy.** Every queryset is `tenant=request.tenant`-scoped, never
  `.all()`. `request.tenant` is `None` for the `admin` superuser; an empty
  report is the correct answer for them, never a 500.
* **Never sum across currencies.** A workspace can hold several currencies, so
  a total is only produced when the rows share a single reporting currency.
  Anything else becomes a `caveats` entry rather than a wrong number (L29).
"""
from collections import OrderedDict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.crm.models import Opportunity
from apps.sales.forecast_services import forecast_ai_gate, forecast_org_unit_chain
from apps.sales.models.SalesForecasting.ForecastAdjustments import ForecastAdjustment
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.SalesForecasting.ForecastScenarios import ForecastScenario
from apps.sales.models.SalesForecasting.ForecastSubmissions import ForecastSubmission
from apps.sales.views.SalesForecasting.ForecastPeriods import _is_tenant_admin
from apps.sales.views._common import *  # noqa: F401,F403

TEMPLATE_BOARD = "sales/salesforecasting/forecastboard/board.html"
TEMPLATE_ATTAINMENT = "sales/salesforecasting/forecastboard/attainment.html"
TEMPLATE_ACCURACY = "sales/salesforecasting/forecastboard/accuracy.html"
TEMPLATE_CALL = "sales/salesforecasting/forecastboard/call.html"

ZERO = Decimal("0")

#: Category -> the `ForecastSubmission` amount column it rolls up from. The
#: vocabulary itself is `crm.Opportunity.FORECAST_CATEGORY_CHOICES`, reused
#: verbatim: 8.4 never re-spells it and never adds a category table.
CATEGORY_AMOUNT_FIELDS = [
    ("omitted", "omitted_amount"),
    ("pipeline", "pipeline_amount"),
    ("best_case", "best_case_amount"),
    ("commit", "commit_amount"),
    ("closed", "closed_amount"),
]
#: The four rollup buckets. `omitted` is an explicit exclusion, not a forecast.
ROLLUP_CATEGORY_FIELDS = [
    ("pipeline", "pipeline_amount"),
    ("best_case", "best_case_amount"),
    ("commit", "commit_amount"),
    ("closed", "closed_amount"),
]

#: Reports are aggregates over at most a few hundred submissions, but the lists
#: are bounded so a huge workspace cannot pull an unbounded set into memory.
MAX_PERIODS = 200
MAX_ROWS = 200


# --------------------------------------------------------------------------- helpers
def _tenant(request):
    """`request.tenant`, or `None` for the tenantless superuser."""
    return getattr(request, "tenant", None)


def _sum(values):
    total = ZERO
    for value in values:
        total += value or ZERO
    return total


def _safe_pct(numerator, denominator):
    """``(numerator / denominator) * 100`` or ``None``.

    ``None`` — rendered as an em dash — rather than ``Infinity``/``NaN``, because
    ``Decimal`` division by zero raises and float division silently poisons the
    page with a non-finite value.
    """
    if denominator in (None, 0, ZERO):
        return None
    return (Decimal(numerator) / Decimal(denominator)) * Decimal(100)


def _periods(tenant, only_past=False):
    """The period filter list, bounded. Empty for the tenantless superuser."""
    if tenant is None:
        return []
    qs = ForecastPeriod.objects.filter(tenant=tenant).select_related("reporting_currency")
    if only_past:
        today = timezone.localdate()
        qs = qs.filter(end_date__lt=today)
    return list(qs.order_by("-start_date", "-period_year", "-period_number")[:MAX_PERIODS])


def _period_choices(periods):
    return [(p.pk, str(p)) for p in periods]


def _selected_period(tenant, request, periods):
    """The `?period=<pk>` selection, validated against *this* tenant's periods.

    A junk `?period=abc` or a foreign tenant's pk must not 500 and must not leak
    the other tenant's row, so the id is only honoured when it matches a period
    the caller can already see.
    """
    raw = (request.GET.get("period") or "").strip()
    if raw:
        try:
            wanted = int(raw)
        except (TypeError, ValueError):
            return None
        for period in periods:
            if period.pk == wanted:
                return period
        return None
    return periods[0] if periods else None


def _submissions(tenant, period):
    """`ForecastSubmission` rows for a period, scoped to the tenant."""
    if tenant is None or period is None:
        return []
    qs = ForecastSubmission.objects.filter(tenant=tenant, period=period).select_related(
        "owner", "org_unit", "territory", "pipeline"
    )
    return list(qs.order_by("owner__last_name", "owner__first_name", "pk"))


def _adjustments(tenant, period, submission_ids=None):
    if tenant is None or period is None:
        return []
    qs = ForecastAdjustment.objects.filter(
        tenant=tenant, submission__period=period
    ).select_related("submission", "submission__owner", "created_by", "opportunity")
    if submission_ids is not None:
        qs = qs.filter(submission_id__in=list(submission_ids))
    return list(qs.order_by("pk"))


def _scenarios(tenant, period):
    if tenant is None or period is None:
        return []
    return list(
        ForecastScenario.objects.filter(tenant=tenant, period=period).select_related("owner")
    )


def _category_amounts(submission):
    """``{category: Decimal}`` for one submission, off its amount columns."""
    return OrderedDict(
        (category, getattr(submission, field) or ZERO)
        for category, field in CATEGORY_AMOUNT_FIELDS
    )


def _single_currency(period):
    """The period's reporting-currency code, or ``None`` when it has none.

    A `ForecastPeriod` declares exactly ONE `reporting_currency`, so every
    submission in a period is commensurable by construction and a total is
    always safe — provided the period actually set one. A period with no
    reporting currency returns ``None``, and the caller records a caveat
    instead of printing an unqualified grand total (L29).
    """
    if period is None:
        return None
    currency = getattr(period, "reporting_currency", None)
    return getattr(currency, "code", None) or None


def _label(user, org_unit, territory):
    """The most specific human label available for a rollup node."""
    if user is not None:
        return user.get_full_name() or user.get_username()
    if org_unit is not None:
        return getattr(org_unit, "name", None) or str(org_unit)
    if territory is not None:
        return getattr(territory, "name", None) or str(territory)
    return "Unassigned"


def _rollup_nodes(submissions, rollup_dimension):
    """Group submissions into one row per rollup node.

    The axis is whatever the period declares: `user` (a rep), `org_unit` (the
    `core.OrgUnit.parent` walk) or `territory`. An unknown or empty value falls
    back to a single ungrouped tenant total rather than erroring.
    """
    grouped = OrderedDict()
    for submission in submissions:
        if rollup_dimension == "user":
            node = submission.owner
        elif rollup_dimension == "org_unit":
            node = submission.org_unit
        elif rollup_dimension == "territory":
            node = submission.territory
        else:
            node = None
        depth = 0
        if rollup_dimension == "org_unit" and node is not None:
            depth = max(len(forecast_org_unit_chain(node)) - 1, 0)
        key = node.pk if node is not None else "unassigned"
        bucket = grouped.setdefault(key, {"node": node, "depth": depth, "submissions": []})
        bucket["submissions"].append(submission)

    rows = []
    for key, bucket in list(grouped.items())[:MAX_ROWS]:
        node = bucket["node"]
        rows.append(
            {
                "key": key,
                "label": _label(
                    node if rollup_dimension == "user" else None,
                    node if rollup_dimension == "org_unit" else None,
                    node if rollup_dimension == "territory" else None,
                ),
                "owner": node if rollup_dimension == "user" else None,
                "org_unit": node if rollup_dimension == "org_unit" else None,
                "territory": node if rollup_dimension == "territory" else None,
                "submissions": bucket["submissions"],
                "child_count": len(bucket["submissions"]),
                "depth": bucket["depth"],
            }
        )
    return rows


# --------------------------------------------------------------------------- 1. board
@login_required
def forecast_board(request):
    """The rep -> manager -> director rollup board for one forecast period."""
    tenant = _tenant(request)
    periods = _periods(tenant)
    period = _selected_period(tenant, request, periods)
    rollup_dimension = (request.GET.get("rollup_dimension") or "").strip()
    rollup_choices = ForecastPeriod.ROLLUP_DIMENSION_CHOICES
    if rollup_dimension and rollup_dimension not in dict(rollup_choices):
        # A junk value narrows to nothing rather than exploding; the register
        # below still renders in full.
        rollup_dimension = ""

    submissions = _submissions(tenant, period)
    rows = _rollup_nodes(submissions, rollup_dimension)
    ai_available, ai_gate_message = forecast_ai_gate(tenant)
    caveats = []

    currency_code = _single_currency(period)
    if submissions and currency_code is None:
        caveats.append(
            "This period has no reporting currency, so the totals below are not "
            "labelled with a currency code. Set one on the period to remove this."
        )

    for row in rows:
        bucket = row["submissions"]
        per_category = OrderedDict(
            (category, _sum(getattr(s, field) for s in bucket))
            for category, field in ROLLUP_CATEGORY_FIELDS
        )
        row["per_category"] = per_category
        row["total_forecast_amount"] = _sum(per_category.values())
        row["weighted_amount"] = _sum(s.weighted_amount for s in bucket)
        row["quota_amount"] = _sum(s.quota_amount for s in bucket)
        row["actual_amount"] = _sum(s.actual_amount for s in bucket)
        row["attainment_pct"] = _safe_pct(row["total_forecast_amount"], row["quota_amount"])
        row["variance_amount"] = row["total_forecast_amount"] - row["actual_amount"]
        # Prediction figures render only when the AI gate actually passed — a
        # gated-off workspace must show no prediction value at all.
        row["ai_predicted_commit"] = (
            _sum(s.ai_predicted_commit or ZERO for s in bucket) if ai_available else None
        )
        row["ai_confidence_pct"] = (
            _safe_pct(_sum(s.ai_confidence_pct or 0 for s in bucket), len(bucket))
            if ai_available
            else None
        )
        row["ai_explanation"] = {}
        if row["quota_amount"] == 0:
            caveats.append("%s has no quota recorded, so attainment is not shown." % row["label"])

    totals_by_category = OrderedDict(
        (category, _sum(row["per_category"].get(category, ZERO) for row in rows))
        for category, _ in ROLLUP_CATEGORY_FIELDS
    )
    grand_total = _sum(totals_by_category.values())
    # A template cannot index a dict by a loop variable, so the per-category
    # totals are also handed over pre-zipped as (value, label, amount) rows.
    category_labels = dict(Opportunity.FORECAST_CATEGORY_CHOICES)
    category_total_rows = [
        (category, category_labels.get(category, category), totals_by_category.get(category, ZERO))
        for category, _ in ROLLUP_CATEGORY_FIELDS
    ]

    adjustments = _adjustments(tenant, period)
    scenarios = _scenarios(tenant, period)
    explanation = {}
    for submission in submissions:
        if ai_available and submission.ai_explanation:
            explanation = submission.ai_explanation
            break

    return render(
        request,
        TEMPLATE_BOARD,
        {
            "period": period,
            "periods": periods,
            "period_choices": _period_choices(periods),
            "category_choices": Opportunity.FORECAST_CATEGORY_CHOICES,
            "rows": rows,
            "totals_by_category": totals_by_category,
            "category_total_rows": category_total_rows,
            "grand_total": grand_total,
            "currency_code": currency_code,
            "ai_available": ai_available,
            "ai_gate_message": ai_gate_message,
            "ai_explanation": explanation,
            "rollup_dimension": rollup_dimension,
            "rollup_dimension_choices": rollup_choices,
            "caveats": caveats,
            "stats": {
                "periods": len(periods),
                "submissions": len(submissions),
                "approved": len([s for s in submissions if s.status == "approved"]),
                "adjustments": len(adjustments),
                "scenarios": len(scenarios),
            },
        },
    )


# --------------------------------------------------------------------- 2. attainment
@login_required
def forecast_attainment(request):
    """Quota vs. forecast attainment per rep, against the period's pace benchmark."""
    tenant = _tenant(request)
    periods = _periods(tenant)
    period = _selected_period(tenant, request, periods)
    submissions = _submissions(tenant, period)
    caveats = []

    grouped = OrderedDict()
    for submission in submissions:
        bucket = grouped.setdefault(
            submission.owner_id, {"owner": submission.owner, "submissions": []}
        )
        bucket["submissions"].append(submission)

    pace_pct = getattr(period, "period_elapsed_pct", None)
    rows = []
    for bucket in list(grouped.values())[:MAX_ROWS]:
        bucket_rows = bucket["submissions"]
        quota_amount = _sum(s.quota_amount for s in bucket_rows)
        actual_amount = _sum(s.actual_amount for s in bucket_rows)
        forecast_amount = _sum(
            getattr(s, field) or ZERO for s in bucket_rows for _, field in ROLLUP_CATEGORY_FIELDS
        )
        rows.append(
            {
                "owner": bucket["owner"],
                "org_unit": bucket_rows[0].org_unit if bucket_rows else None,
                "territory": bucket_rows[0].territory if bucket_rows else None,
                "quota_amount": quota_amount,
                "actual_amount": actual_amount,
                "forecast_amount": forecast_amount,
                "attainment_pct": _safe_pct(forecast_amount, quota_amount),
                "pace_pct": pace_pct,
                "variance_amount": forecast_amount - actual_amount,
            }
        )

    def _band(row):
        # A rep with no quota cannot be banded against a pace, so they are
        # reported as "no quota" rather than silently counted as behind.
        if row["attainment_pct"] is None or pace_pct is None:
            return "no_quota"
        return "ahead" if row["attainment_pct"] >= pace_pct else "behind"

    ahead_rows = [r for r in rows if _band(r) == "ahead"]
    behind_rows = [r for r in rows if _band(r) == "behind"]
    on_pace_rows = [r for r in rows if _band(r) == "no_quota"]
    if any(r["attainment_pct"] is None for r in rows):
        caveats.append(
            "A rep with no quota recorded cannot be banded, so they are listed under "
            "'no quota' rather than being counted as behind."
        )
    if pace_pct is None:
        caveats.append("This period has no elapsed-time benchmark yet.")

    return render(
        request,
        TEMPLATE_ATTAINMENT,
        {
            "period": period,
            "periods": periods,
            "period_choices": _period_choices(periods),
            "rows": rows,
            "pace_pct": pace_pct,
            "ahead_rows": ahead_rows,
            "behind_rows": behind_rows,
            "on_pace_rows": on_pace_rows,
            "caveats": caveats,
            "can_edit_all": _is_tenant_admin(request.user),
            "stats": {
                "total": len(rows),
                "ahead": len(ahead_rows),
                "on_pace": len(on_pace_rows),
                "behind": len(behind_rows),
                "no_quota": len([r for r in rows if r["attainment_pct"] is None]),
            },
        },
    )


# ----------------------------------------------------------------------- 3. accuracy
@login_required
def forecast_accuracy(request):
    """Actual vs. predicted per period, plus per-owner bias and sandbagging."""
    tenant = _tenant(request)
    periods = _periods(tenant, only_past=True)
    selected_period_id = None
    raw = (request.GET.get("period") or "").strip()
    if raw:
        try:
            selected_period_id = int(raw)
        except (TypeError, ValueError):
            selected_period_id = None

    rows = []
    bias_by_owner = OrderedDict()
    sandbagging_by_owner = OrderedDict()
    caveats = []
    bias_values = []

    for period in periods[:MAX_PERIODS]:
        submissions = _submissions(tenant, period)
        if not submissions:
            continue
        submitted_total = _sum(
            getattr(s, field) or ZERO for s in submissions for _, field in ROLLUP_CATEGORY_FIELDS
        )
        actual_amount = _sum(s.actual_amount for s in submissions)
        # Bias is signed on purpose: a negative number is a rep who consistently
        # forecasts under the eventual outcome — the sandbagging signal.
        bias_pct = None
        if submitted_total and actual_amount:
            bias_pct = ((submitted_total - actual_amount) / actual_amount) * Decimal(100)
            bias_values.append(bias_pct)
        adjustments = _adjustments(tenant, period, [s.pk for s in submissions])
        rows.append(
            {
                "period": period,
                "label": period.label,
                "submitted_total": submitted_total,
                "actual_amount": actual_amount,
                "variance_amount": submitted_total - actual_amount,
                "bias_pct": bias_pct,
                "weight_bias": _safe_pct(
                    _sum(s.weighted_amount for s in submissions), submitted_total
                ),
                "adjustment_count": len(adjustments),
            }
        )

        for submission in submissions:
            forecast_amount = _sum(
                getattr(submission, field) or ZERO for _, field in ROLLUP_CATEGORY_FIELDS
            )
            bucket = bias_by_owner.setdefault(
                submission.owner_id, {"owner": submission.owner, "total": ZERO, "count": 0}
            )
            if submission.actual_amount:
                bucket["total"] += (
                    (forecast_amount - submission.actual_amount) / submission.actual_amount
                ) * Decimal(100)
                bucket["count"] += 1

        for adjustment in adjustments:
            if adjustment.is_reverted:
                continue
            bucket = sandbagging_by_owner.setdefault(
                adjustment.submission.owner_id,
                {
                    "owner": adjustment.submission.owner,
                    "net_delta": ZERO,
                    "adjustment_count": 0,
                },
            )
            bucket["adjustment_count"] += 1
            bucket["net_delta"] += adjustment.net_delta or ZERO

    bias_rows = []
    for bucket in bias_by_owner.values():
        if not bucket["count"]:
            continue
        mean_bias = bucket["total"] / Decimal(bucket["count"])
        bias_values.append(mean_bias)
        bias_rows.append(
            {
                "owner": bucket["owner"],
                "mean_bias_pct": mean_bias,
                "submissions": bucket["count"],
            }
        )
    bias_rows.sort(key=lambda r: r["mean_bias_pct"])

    sandbagging_rows = sorted(
        (
            {
                "owner": bucket["owner"],
                "net_delta": bucket["net_delta"],
                "adjustment_count": bucket["adjustment_count"],
            }
            for bucket in sandbagging_by_owner.values()
        ),
        key=lambda r: r["net_delta"],
    )

    if not rows:
        caveats.append("No past period has a recorded forecast to compare against actuals yet.")
    mean_bias_pct = (sum(bias_values, ZERO) / Decimal(len(bias_values))) if bias_values else None
    worst_biased_owner = bias_rows[0]["owner"] if bias_rows else None

    return render(
        request,
        TEMPLATE_ACCURACY,
        {
            "periods": periods,
            "period_choices": _period_choices(periods),
            "selected_period_id": selected_period_id,
            "rows": rows,
            "bias_rows": bias_rows,
            "sandbagging_rows": sandbagging_rows,
            "caveats": caveats,
            "stats": {
                "periods": len(rows),
                "mean_bias_pct": mean_bias_pct,
                "worst_biased_owner": worst_biased_owner,
            },
        },
    )


# -------------------------------------------------------------------------- 4. call
@login_required
def forecast_call(request):
    """The per-rep forecast call: every submission and every override on it."""
    tenant = _tenant(request)
    periods = _periods(tenant)
    period = _selected_period(tenant, request, periods)
    submissions = _submissions(tenant, period)
    ai_available, ai_gate_message = forecast_ai_gate(tenant)
    caveats = []

    submission_rows = []
    explanation = {}
    for submission in submissions:
        total = _sum(getattr(submission, field) or ZERO for _, field in ROLLUP_CATEGORY_FIELDS)
        submission_rows.append(
            {
                "submission": submission,
                "owner": submission.owner,
                "org_unit": submission.org_unit,
                "territory": submission.territory,
                "category_amounts": _category_amounts(submission),
                "total_forecast_amount": total,
                "status": submission.status,
                "submitted_at": submission.submitted_at,
            }
        )
        if ai_available and submission.ai_explanation and not explanation:
            explanation = submission.ai_explanation

    # "Why did my forecast change" — every override, reverted ones included, so
    # the audit trail stays visible rather than disappearing on reset.
    adjustment_rows = [
        {
            "adjustment": adjustment,
            "reason_code": adjustment.reason_code,
            "created_by": adjustment.created_by,
            "note": adjustment.note,
            "is_reverted": adjustment.is_reverted,
            "net_delta": adjustment.net_delta,
        }
        for adjustment in _adjustments(tenant, period, [s.pk for s in submissions])
    ]

    if period is not None and period.is_locked:
        caveats.append("This period is locked, so submissions are read-only.")
    if not submission_rows:
        caveats.append("No rep has submitted a call for this period yet.")

    return render(
        request,
        TEMPLATE_CALL,
        {
            "period": period,
            "periods": periods,
            "period_choices": _period_choices(periods),
            "submission_rows": submission_rows,
            "adjustment_rows": adjustment_rows,
            "ai_available": ai_available,
            "ai_gate_message": ai_gate_message,
            "ai_explanation": explanation,
            "caveats": caveats,
            "can_review": _is_tenant_admin(request.user),
        },
    )
