"""SCM 4.7 Demand Planning — computed reports (no CRUD models of their own).

Two pages, mirroring 4.3's ``InventoryManagement/Reports.py``:

* **Safety Stock** — the NavERP 4.7 "Safety Stock Calculation" bullet. Every active ``ReorderRule``
  with its calculated policy numbers next to the live ones, a batch **Recalculate** and a per-rule
  **Apply**. The report itself only READS stored columns: the derivation happens in the explicit
  recalculate action, so opening the page never fires a per-row aggregate.
* **Forecast Accuracy** — a MAPE/WMAPE/bias/tracking-signal/FVA league table with the exception rows
  flagged. Not a NavERP bullet; it is where the module's exception management lives.
"""
from datetime import timedelta
from urllib.parse import urlencode

from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _item_qs, _location_qs, _need_tenant
from apps.scm.models import DemandForecast, ReorderRule
from apps.scm.models.DemandPlanning._history import demand_series_map

ZERO = Decimal("0")

#: |bias| and |tracking signal| beyond these mean the model is drifting, not just noisy.
BIAS_EXCEPTION_PCT = Decimal("20")
TRACKING_SIGNAL_EXCEPTION = Decimal("4")

#: The safety-stock page's filter params. Whitelisted rather than echoing the whole request, so the
#: post-recalculate redirect can never carry the CSRF token (or anything else) into a URL.
_SAFETY_FILTERS = ("q", "safety_stock_method", "item", "location")


def _filtered_rules(request, data=None):
    """The active rules a safety-stock page is looking at.

    ``data`` lets the recalculate POST reuse the exact filter spec the report rendered with, so
    "Recalculate" always means "recalculate what is on screen" rather than "recalculate everything".
    """
    data = request.GET if data is None else data
    qs = (ReorderRule.objects.filter(tenant=request.tenant, is_active=True)
          .select_related("item", "location", "seasonality_profile", "demand_forecast"))
    q = data.get("q", "").strip()
    if q:
        qs = qs.filter(Q(item__sku__icontains=q) | Q(item__name__icontains=q)
                       | Q(location__code__icontains=q))
    method = data.get("safety_stock_method", "").strip()
    if method:
        qs = qs.filter(safety_stock_method=method)
    for param, lookup in (("item", "item_id"), ("location", "location_id")):
        value = data.get(param, "").strip()
        if value.isdigit():  # L11: never hand a non-numeric value to an int FK filter
            qs = qs.filter(**{lookup: int(value)})
    return qs


def _safety_report_url(data):
    """Back to the report with the same filters — whitelist only (see _SAFETY_FILTERS)."""
    params = {key: data.get(key, "").strip() for key in _SAFETY_FILTERS}
    query = urlencode({key: value for key, value in params.items() if value})
    url = reverse("scm:safety_stock_report")
    return f"{url}?{query}" if query else url


@login_required
def safety_stock_report(request):
    """Calculated vs. live safety stock and reorder point for every active rule."""
    rules = list(_filtered_rules(request))
    # ONE grouped query for every rule's on-hand (the 4.3 precedent) — the page shows stored
    # computed_* figures, so nothing else is derived per row.
    qty_map = ReorderRule.on_hand_map(request.tenant, rules)
    rows = []
    for rule in rules:
        rows.append({
            "rule": rule,
            "on_hand": qty_map.get((rule.item_id, rule.location_id), ZERO),
            "variance": rule.safety_stock_variance,
            "variance_pct": rule.safety_stock_variance_pct,
        })
    rows.sort(key=lambda row: abs(row["variance"]), reverse=True)
    return render(request, "scm/demandplanning/safety_stock_report.html", {
        "rows": rows,
        "method_choices": ReorderRule.SAFETY_STOCK_METHOD_CHOICES,
        "items": _item_qs(request.tenant),
        "locations": _location_qs(request.tenant),
        "q": request.GET.get("q", "").strip(),
        "uncalculated": sum(1 for rule in rules if rule.last_calculated_at is None),
    })


@login_required
@require_POST
def safety_stock_recalculate(request):
    """Recalculate the filtered rules' policy numbers.

    Writes ONLY the ``computed_*``/statistics columns — never the live ``safety_stock``/
    ``reorder_point`` that 4.3's reorder alerts and suggested quantities read. Promoting a
    recommendation is a separate, per-rule decision (see ``safety_stock_apply``).
    """
    if _need_tenant(request):
        return redirect("scm:safety_stock_report")
    rules = list(_filtered_rules(request, data=request.POST))
    if not rules:
        messages.info(request, "No active reorder rules match — create one first.")
        return redirect(_safety_report_url(request.POST))
    end = timezone.localdate()
    start = end - timedelta(days=30 * ReorderRule.CALC_HISTORY_MONTHS)
    # One grouped history query for every item, then each rule is sized from its slice — deriving
    # per rule would be one aggregate per row.
    series_map = demand_series_map(request.tenant, {rule.item_id for rule in rules},
                                   start=start, end=end, bucket="month")
    ReorderRule.assign_abc_classes(request.tenant, rules)
    for rule in rules:
        rule.calculate(series=series_map.get(rule.item_id, []))
    ReorderRule.objects.bulk_update(
        rules, ["avg_daily_demand", "demand_std_dev", "abc_class", "xyz_class",
                "computed_safety_stock", "computed_reorder_point", "last_calculated_at"])
    # A batch action has no single target object — `obj=None` + an explicit tenant is the codebase's
    # shape for one (crm HealthScores.recompute, hrm leave-policy actions).
    write_audit_log(request.user, None, "update",
                    {"action": "safety_stock_recalculate", "rules": len(rules)},
                    tenant=request.tenant)
    messages.success(request, f"Recalculated {len(rules)} rules. Nothing was applied — review the "
                              f"variance and apply the ones you agree with.")
    return redirect(_safety_report_url(request.POST))


@tenant_admin_required
@require_POST
def safety_stock_apply(request, pk):
    """Promote ONE rule's calculated numbers into the live columns.

    A privileged write: these two columns drive 4.1 purchasing through 4.3's reorder alerts, so
    changing them is a buying decision, not a report refresh.
    """
    rule = get_object_or_404(ReorderRule, pk=pk, tenant=request.tenant)
    if rule.last_calculated_at is None:
        messages.error(request, "Recalculate this rule before applying it.")
        return redirect(_safety_report_url(request.POST))
    changes = rule.apply_computed()
    write_audit_log(request.user, rule, "update", {"action": "apply_safety_stock", **changes})
    messages.success(request, f"Applied the calculated policy to {rule.item.sku} @ "
                              f"{rule.location.code}.")
    return redirect(_safety_report_url(request.POST))


@login_required
def forecast_accuracy_report(request):
    """MAPE / WMAPE / bias / tracking signal / FVA per forecast, with the exceptions flagged."""
    forecasts = list(DemandForecast.objects
                     .filter(tenant=request.tenant)
                     .exclude(status="draft")
                     .select_related("item", "location")
                     .prefetch_related("periods"))
    # Group by (bucket, demand_source) so the actuals for every forecast in a group come from ONE
    # grouped query instead of one per forecast. The SOURCE has to be part of the key: scoring a
    # stock-issues forecast against sales orders would report a different WMAPE here than the same
    # forecast's own detail page, which reads its own configured ledger.
    grouped = {}
    for forecast in forecasts:
        grouped.setdefault((forecast.bucket, forecast.demand_source), []).append(forecast)
    rows = []
    for (bucket, source), group in grouped.items():
        start = min(f.horizon_start for f in group)
        end = max(f.horizon_end for f in group)
        series_map = demand_series_map(request.tenant, {f.item_id for f in group},
                                       start=start, end=end, bucket=bucket, source=source)
        for forecast in group:
            # The batch map is item-level. A customer-scoped forecast must not be graded against
            # every channel's demand, so it pays for its own exact series — rare enough that one
            # extra query beats a wrong number on a league table.
            actuals = (forecast.period_actuals_map() if forecast.customer_id
                       else dict(series_map.get(forecast.item_id, [])))
            periods = list(forecast.periods.all())
            metrics = forecast.accuracy_metrics(periods=periods, actuals=actuals)
            bias, signal = metrics["bias_pct"], metrics["tracking_signal"]
            rows.append({
                "forecast": forecast,
                "metrics": metrics,
                "is_exception": ((bias is not None and abs(bias) > BIAS_EXCEPTION_PCT)
                                 or (signal is not None
                                     and abs(signal) > TRACKING_SIGNAL_EXCEPTION)),
            })
    # Exceptions first, then worst WMAPE — the two things a planner opens this page to find.
    rows.sort(key=lambda row: (not row["is_exception"],
                               -(row["metrics"]["wmape"] or ZERO)))
    return render(request, "scm/demandplanning/forecast_accuracy_report.html", {
        "rows": rows,
        "scored": sum(1 for row in rows if row["metrics"]["points"]),
        "exceptions": sum(1 for row in rows if row["is_exception"]),
        "bias_threshold": BIAS_EXCEPTION_PCT,
        "signal_threshold": TRACKING_SIGNAL_EXCEPTION,
    })
