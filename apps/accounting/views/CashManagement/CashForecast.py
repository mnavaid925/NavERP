"""Accounting 2.5 Cash Management — CashForecast views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _cash_position
from apps.accounting.models import (
    Bill,
    Invoice,
    ZERO,
)


@login_required
def cash_forecast(request):
    """2.1 Cash-flow forecast — projects the cash position forward from open AR (expected inflows)
    and open AP (expected outflows), bucketed weekly by due date. Overdue / no-due-date items roll
    into the first week (assumed to settle now); amounts due beyond the horizon are reported
    separately. Deterministic (no ML): every figure traces to a real open invoice/bill plus the
    live cash position. ``?weeks=`` (4–52, default 13) sets the horizon."""
    tenant = request.tenant
    try:
        weeks = int(request.GET.get("weeks", 13))
    except (TypeError, ValueError):
        weeks = 13
    weeks = max(4, min(52, weeks))

    rows, chart_labels, chart_balance = [], [], []
    stats = {"opening": ZERO, "inflow": ZERO, "outflow": ZERO, "projected": ZERO,
             "low_balance": ZERO, "beyond_inflow": ZERO, "beyond_outflow": ZERO}
    if tenant is not None:
        today = timezone.localdate()
        opening = _cash_position(tenant)
        first_monday = today - timedelta(days=today.weekday())
        buckets = [{"start": first_monday + timedelta(weeks=i), "inflow": ZERO, "outflow": ZERO}
                   for i in range(weeks)]
        horizon_end = buckets[-1]["start"] + timedelta(days=6)

        def _idx(due):
            # No due date or overdue → first week; beyond horizon → None (reported separately).
            if due is None or due < first_monday:
                return 0
            if due > horizon_end:
                return None
            return (due - first_monday).days // 7

        # Only true invoices are expected cash inflows. A credit note (kind="credit_note") carries a
        # positive total but economically REDUCES receivables (a refund/offset, not money in), so it
        # must not be projected as inflow — exclude it (adversarial-review finding).
        invoices = (Invoice.objects.filter(tenant=tenant, status__in=Invoice.OPEN_STATUSES, kind="invoice")
                    .annotate(paid_agg=Sum("allocations__allocated_amount",
                                           filter=Q(allocations__payment__status="confirmed"))))
        for inv in invoices:
            amt = (inv.total or ZERO) - (inv.paid_agg or ZERO)
            if amt <= ZERO:
                continue
            idx = _idx(inv.due_date)
            if idx is None:
                stats["beyond_inflow"] += amt
            else:
                buckets[idx]["inflow"] += amt

        bills = (Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES)
                 .annotate(paid_agg=Sum("allocations__allocated_amount",
                                        filter=Q(allocations__payment__status="confirmed"))))
        for bill in bills:
            amt = (bill.total or ZERO) - (bill.paid_agg or ZERO)
            if amt <= ZERO:
                continue
            idx = _idx(bill.due_date)
            if idx is None:
                stats["beyond_outflow"] += amt
            else:
                buckets[idx]["outflow"] += amt

        running, low, total_in, total_out = opening, opening, ZERO, ZERO
        for b in buckets:
            net = b["inflow"] - b["outflow"]
            running += net
            low = min(low, running)
            total_in += b["inflow"]
            total_out += b["outflow"]
            rows.append({"start": b["start"], "end": b["start"] + timedelta(days=6),
                         "inflow": b["inflow"], "outflow": b["outflow"], "net": net,
                         "balance": running})
            chart_labels.append(b["start"].strftime("%b %d"))
            chart_balance.append(float(running))
        stats.update({"opening": opening, "inflow": total_in, "outflow": total_out,
                      "projected": running, "low_balance": low})
    return render(request, "accounting/cash/forecast.html", {
        "rows": rows, "stats": stats, "weeks": weeks, "weeks_options": [4, 8, 13, 26, 52],
        "chart_labels": chart_labels, "chart_balance": chart_balance,
        "today": timezone.localdate(),
    })
