"""CRM 1.2 Sales Force Automation — Forecast views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Opportunity,
    SalesQuota,
)


_ZERO = Decimal("0")
_UNSPECIFIED_CURRENCY = "Unspecified"


def _forecast_currency_label(code):
    value = str(code).strip().upper() if code else ""
    return value or _UNSPECIFIED_CURRENCY


def _forecast_currency_row(currency_id, code, **values):
    label = _forecast_currency_label(code)
    row = {
        "currency_id": currency_id,
        "currency_code": label,
        "currency_label": label,
    }
    row.update(values)
    return row


def _forecast_currency_sort(row):
    label = row.get("currency_label") or _UNSPECIFIED_CURRENCY
    return (label == _UNSPECIFIED_CURRENCY, label)


def _forecast_ensure_row(rows, currency_id, code):
    row = rows.get(currency_id)
    if row is None:
        row = _forecast_currency_row(
            currency_id,
            code,
            count=0,
            pipeline=_ZERO,
            weighted=_ZERO,
            won=_ZERO,
            target=_ZERO,
        )
        rows[currency_id] = row
    return row


def _forecast_metric_scalar(rows, metric):
    if len(rows) > 1:
        return None
    if not rows:
        return _ZERO
    return rows[0][metric]


def _forecast_empty_totals():
    return {
        "pipeline": _ZERO,
        "weighted": _ZERO,
        "won": _ZERO,
        "target": _ZERO,
        "currency_rows": [],
        "pipeline_currency_rows": [],
        "weighted_currency_rows": [],
        "won_currency_rows": [],
        "target_currency_rows": [],
        "mixed_currency": False,
        "currency_label": _UNSPECIFIED_CURRENCY,
        "pipeline_mixed_currency": False,
        "weighted_mixed_currency": False,
        "won_mixed_currency": False,
        "target_mixed_currency": False,
    }


def _forecast_empty_won_bucket():
    return {"amount": _ZERO, "count": 0}


def _forecast_add_won(rows, currency_id, code, amount, count):
    bucket = rows.setdefault(
        currency_id,
        _forecast_empty_won_bucket(),
    )
    bucket["amount"] += amount
    bucket["count"] += count


@login_required
def forecast(request):
    """Weighted-pipeline-by-forecast-category + quota-attainment dashboard (DB-side aggregates)."""
    tenant = request.tenant
    cats = []
    quotas = []
    totals = _forecast_empty_totals()
    chart_labels = []
    chart_data = []
    chart_available = False
    chart_empty_reason = "No opportunities to forecast."
    chart_currency_label = _UNSPECIFIED_CURRENCY

    if tenant is not None:
        opps = Opportunity.objects.filter(tenant=tenant)
        opportunity_rows = list(
            opps.values("forecast_category", "stage", "currency_id", "currency__code")
            .annotate(
                count=Count("id"),
                total=Sum("amount"),
                weighted_sum=Sum(
                    F("amount") * F("probability"),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                ),
            )
            .order_by("forecast_category", "stage", "currency__code", "currency_id")
        )
        category_rows = {}
        all_currency_rows = {}
        pipeline_currency_rows = {}
        weighted_currency_rows = {}
        won_currency_rows = {}
        for raw in opportunity_rows:
            currency_id = raw["currency_id"]
            code = raw["currency__code"]
            total = Decimal(raw["total"] or 0)
            weighted = Decimal(raw["weighted_sum"] or 0) / Decimal(100)
            count = raw["count"] or 0
            category_bucket = category_rows.setdefault(raw["forecast_category"], {})
            category_row = category_bucket.get(currency_id)
            if category_row is None:
                category_row = _forecast_currency_row(
                    currency_id,
                    code,
                    count=0,
                    total=_ZERO,
                    weighted=_ZERO,
                )
                category_bucket[currency_id] = category_row
            category_row["count"] += count
            category_row["total"] += total
            category_row["weighted"] += weighted
            category_row["amount"] = category_row["total"]
            category_row["weighted_amount"] = category_row["weighted"]
            all_row = _forecast_ensure_row(all_currency_rows, currency_id, code)
            all_row["count"] += count
            if raw["stage"] in Opportunity.OPEN_STAGES:
                pipeline_row = _forecast_ensure_row(pipeline_currency_rows, currency_id, code)
                pipeline_row["pipeline"] += total
                all_row["pipeline"] += total
                weighted_row = _forecast_ensure_row(weighted_currency_rows, currency_id, code)
                weighted_row["weighted"] += weighted
                all_row["weighted"] += weighted
            elif raw["stage"] == "closed_won":
                won_row = _forecast_ensure_row(won_currency_rows, currency_id, code)
                won_row["won"] += total
                all_row["won"] += total

        category_labels = dict(Opportunity.FORECAST_CATEGORY_CHOICES)
        for category_value in sorted(
            category_rows,
            key=lambda value: str(value or ""),
        ):
            rows = sorted(category_rows[category_value].values(), key=_forecast_currency_sort)
            mixed = len(rows) > 1
            cats.append(
                {
                    "forecast_category": category_value,
                    "label": category_labels.get(category_value, category_value),
                    "count": sum(row["count"] for row in rows),
                    "total": rows[0]["total"] if len(rows) == 1 else None,
                    "weighted": rows[0]["weighted"] if len(rows) == 1 else None,
                    "currency_rows": rows,
                    "mixed_currency": mixed,
                    "currency_label": rows[0]["currency_label"] if len(rows) == 1 else "Mixed currencies",
                    "comparable": not mixed,
                }
            )

        won_rows = list(
            opps.filter(stage="closed_won")
            .values("owner_id", "territory_id", "currency_id", "currency__code")
            .annotate(count=Count("id"), total=Sum("amount"))
            .order_by("owner_id", "territory_id", "currency_id")
        )
        won_by_owner_territory = {}
        won_by_owner = {}
        currency_codes = {}
        for raw in won_rows:
            currency_id = raw["currency_id"]
            code = raw["currency__code"]
            currency_codes.setdefault(currency_id, _forecast_currency_label(code))
            amount = Decimal(raw["total"] or 0)
            count = raw["count"] or 0
            owner_territory_key = (raw["owner_id"], raw["territory_id"])
            owner_key = raw["owner_id"]
            _forecast_add_won(
                won_by_owner_territory.setdefault(owner_territory_key, {}),
                currency_id,
                code,
                amount,
                count,
            )
            _forecast_add_won(
                won_by_owner.setdefault(owner_key, {}),
                currency_id,
                code,
                amount,
                count,
            )

        target_currency_rows = {}
        for quota in SalesQuota.objects.filter(tenant=tenant).select_related("owner", "territory"):
            target = Decimal(quota.target_amount or 0)
            relevant = (
                won_by_owner_territory.get((quota.owner_id, quota.territory_id), {})
                if quota.territory_id
                else won_by_owner.get(quota.owner_id, {})
            )
            keys = set(relevant)
            attained = None
            pct = None
            comparable = False
            reason = ""
            mixed = len(keys) > 1
            if mixed:
                reason = "Closed-won opportunities span multiple currencies."
            elif not keys:
                reason = "No closed-won currency is available."
            elif None in keys:
                reason = "Closed-won currency is unspecified."
            else:
                currency_id = next(iter(keys))
                attained = relevant[currency_id]["amount"]
                pct = max(0, round(float(attained) / float(target) * 100)) if target else 0
                comparable = True
            if len(keys) == 1 and None not in keys:
                target_currency_id = next(iter(keys))
            else:
                target_currency_id = None
            target_row = target_currency_rows.get(target_currency_id)
            if target_row is None:
                target_row = _forecast_currency_row(
                    target_currency_id,
                    currency_codes.get(target_currency_id),
                    target=_ZERO,
                )
                target_currency_rows[target_currency_id] = target_row
            target_row["target"] += target
            quota_currency_rows = []
            for currency_id in sorted(keys, key=lambda value: (
                currency_codes.get(value, _UNSPECIFIED_CURRENCY) == _UNSPECIFIED_CURRENCY,
                currency_codes.get(value, _UNSPECIFIED_CURRENCY),
            )):
                bucket = relevant[currency_id]
                quota_currency_rows.append(
                    _forecast_currency_row(
                        currency_id,
                        currency_codes.get(currency_id),
                        count=bucket["count"],
                        total=bucket["amount"],
                        attained=bucket["amount"],
                    )
                )
            quotas.append(
                {
                    "q": quota,
                    "attained": attained,
                    "pct": pct,
                    "comparable": comparable,
                    "mixed_currency": mixed,
                    "reason": reason,
                    "attainment_reason": reason,
                    "currency_rows": quota_currency_rows,
                    "currency_label": (
                        next(iter(currency_codes.get(key, _UNSPECIFIED_CURRENCY) for key in keys))
                        if len(keys) == 1 and None not in keys
                        else "Mixed currencies" if mixed else "Not comparable"
                    ),
                }
            )

        for currency_id, target_row in target_currency_rows.items():
            all_row = _forecast_ensure_row(
                all_currency_rows,
                currency_id,
                target_row["currency_code"],
            )
            all_row["target"] += target_row["target"]

        pipeline_rows = sorted(pipeline_currency_rows.values(), key=_forecast_currency_sort)
        weighted_rows = sorted(weighted_currency_rows.values(), key=_forecast_currency_sort)
        won_metric_rows = sorted(won_currency_rows.values(), key=_forecast_currency_sort)
        target_rows = sorted(target_currency_rows.values(), key=_forecast_currency_sort)
        all_rows = sorted(all_currency_rows.values(), key=_forecast_currency_sort)
        for row in all_rows:
            row["amount"] = row["pipeline"]
            row["total_amount"] = row["pipeline"]
            row["pipeline_amount"] = row["pipeline"]
            row["weighted_amount"] = row["weighted"]
            row["won_amount"] = row["won"]
            row["target_amount"] = row["target"]
        totals.update(
            {
                "pipeline": _forecast_metric_scalar(pipeline_rows, "pipeline"),
                "weighted": _forecast_metric_scalar(weighted_rows, "weighted"),
                "won": _forecast_metric_scalar(won_metric_rows, "won"),
                "target": _forecast_metric_scalar(target_rows, "target"),
                "currency_rows": all_rows,
                "pipeline_currency_rows": pipeline_rows,
                "weighted_currency_rows": weighted_rows,
                "won_currency_rows": won_metric_rows,
                "target_currency_rows": target_rows,
                "mixed_currency": len(all_rows) > 1,
                "currency_label": (
                    all_rows[0]["currency_label"] if len(all_rows) == 1
                    else "Mixed currencies" if all_rows else _UNSPECIFIED_CURRENCY
                ),
                "pipeline_mixed_currency": len(pipeline_rows) > 1,
                "weighted_mixed_currency": len(weighted_rows) > 1,
                "won_mixed_currency": len(won_metric_rows) > 1,
                "target_mixed_currency": len(target_rows) > 1,
            }
        )
        chart_currency_ids = {
            row["currency_id"]
            for category in cats
            for row in category["currency_rows"]
        }
        chart_available = bool(cats) and len(chart_currency_ids) <= 1
        if chart_available:
            chart_labels = [category["label"] for category in cats]
            chart_data = [float(category["total"] or 0) for category in cats]
            chart_currency_label = cats[0]["currency_label"]
        elif any(category["mixed_currency"] for category in cats):
            chart_empty_reason = "Mixed currencies are not charted without FX conversion."
        elif len(chart_currency_ids) > 1:
            chart_empty_reason = "Forecast categories use multiple currencies and cannot share one chart."
        elif not cats:
            chart_empty_reason = "No opportunities to forecast."

    return render(request, "crm/sales/forecast.html", {
        "cats": cats,
        "quotas": quotas,
        "totals": totals,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "chart_available": chart_available,
        "chart_empty_reason": chart_empty_reason,
        "chart_currency_label": chart_currency_label,
    })
