"""Procurement 6.5 Sourcing & Tendering — Sourcing Analytics.

**Sourcing Analytics** bullet: "Post-event analysis showing savings achieved and market
trends." Everything on this page is DERIVED from the events and bids already in the register —
no snapshot table, no stored aggregates to drift. Figures that cannot be honestly computed are
shown as "—" (None), never as a confident zero: savings only exist where BOTH a budget estimate
and an awarded price exist, cycle time only where the event was actually awarded.

Two queries total (all tenant events, all counted bids), then pure Python: the savings pass and
the month buckets each walk the rows exactly once.
"""
from django.utils import timezone

from apps.procurement.models import SourcingBid, SourcingEvent
from apps.procurement.views._common import *  # noqa: F401,F403


def _month_start(value):
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(month_start, k):
    """Calendar-month arithmetic — fixed 30-day steps duplicate a bucket near month-end."""
    index = month_start.month - 1 + k
    return month_start.replace(year=month_start.year + index // 12,
                               month=index % 12 + 1, day=1)


@login_required
def sourcing_analytics(request):
    now = timezone.now()
    events = list(SourcingEvent.objects.filter(tenant=request.tenant)
                  .select_related("currency"))
    bids = list(SourcingBid.objects
                .filter(tenant=request.tenant,
                        status__in=SourcingBid.COUNTED_STATUSES)
                .select_related("supplier", "event"))
    bids_by_event = {}
    for bid in bids:
        bids_by_event.setdefault(bid.event_id, []).append(bid)

    awarded = [e for e in events if e.status == "awarded"]
    won_bids = {bid.event_id: bid for bid in bids if bid.status == "won"}

    has_budget = False
    total_budget = Decimal("0")
    total_awarded_price = Decimal("0")   # comparable events only — see footnote promise below
    comparable = 0
    savings_rows = []
    cycle_days = []
    participation = []

    for event in awarded:
        won = won_bids.get(event.pk)
        row = {"event": event, "won": won,
               "bids": len(bids_by_event.get(event.pk, [])),
               "budget": event.budget_estimate,
               "price": won.total_price if won else None,
               "savings": None, "savings_pct": None, "cycle_days": None}
        participation.append(row["bids"])
        if event.awarded_at:
            row["cycle_days"] = max((event.awarded_at - event.created_at).days, 0)
            cycle_days.append(row["cycle_days"])
        # Savings exist ONLY where both sides of the comparison exist (review I2): an awarded
        # event without a budget estimate is shown with "—" figures and excluded from the
        # totals, exactly as the page footnote promises.
        if won is not None and event.budget_estimate is not None:
            has_budget = True
            saving = event.budget_estimate - won.total_price
            total_budget += event.budget_estimate
            total_awarded_price += won.total_price
            comparable += 1
            row["savings"] = saving
            if event.budget_estimate > 0:
                row["savings_pct"] = (saving / event.budget_estimate * 100).quantize(
                    Decimal("0.1"))
        savings_rows.append(row)

    def _mean(values):
        # sum()/len() on ints yields a FLOAT — quantize needs a Decimal.
        return (Decimal(sum(values)) / len(values)).quantize(Decimal("0.1")) if values else None

    total_savings = (total_budget - total_awarded_price) if has_budget else None

    # "Market trends" at this layer = participation over recent months, pre-bucketed once
    # (O(N+B)) instead of re-scanning per month; real calendar-month windows so labels never
    # duplicate near month-end.
    first_bucket = _shift_month(_month_start(now), -5)
    buckets = [{"label": _shift_month(first_bucket, i).strftime("%b %Y"),
                "events": 0, "bids": 0}
               for i in range(6)]

    def _bucket_index(moment):
        if moment is None:
            return None
        start = _month_start(moment)
        delta = (start.year - first_bucket.year) * 12 + (start.month - first_bucket.month)
        return delta if 0 <= delta < 6 else None

    for event in events:
        idx = _bucket_index(event.opened_at or event.created_at)
        if idx is not None:
            buckets[idx]["events"] += 1
    for bid in bids:
        idx = _bucket_index(bid.created_at)
        if idx is not None:
            buckets[idx]["bids"] += 1

    return render(request, "procurement/sourcingtendering/analytics.html", {
        "stats": {
            "n_events": len(events),
            "n_open": sum(1 for e in events if e.status == "open"),
            "n_closed": sum(1 for e in events if e.is_evaluating),
            "n_awarded": len(awarded),
            "n_cancelled": sum(1 for e in events if e.status == "cancelled"),
            "total_savings": total_savings,
            "comparable_events": comparable,
            "avg_participation": _mean(participation),
            "avg_cycle_days": _mean(cycle_days),
        },
        "rows": savings_rows,
        "months": [(b["label"], {"events": b["events"], "bids": b["bids"]}) for b in buckets],
    })
