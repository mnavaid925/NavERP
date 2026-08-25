"""Procurement 6.5 Sourcing & Tendering — Sourcing Analytics.

**Sourcing Analytics** bullet: "Post-event analysis showing savings achieved and market
trends." Everything on this page is DERIVED from the events and bids already in the register —
no snapshot table, no stored aggregates to drift. Figures that cannot be honestly computed are
shown as "—" (None), never as a confident zero: savings only exist where BOTH a budget estimate
and an awarded price exist, cycle time only where the event was actually awarded.
"""
from datetime import timedelta

from django.utils import timezone

from apps.procurement.models import SourcingBid, SourcingEvent
from apps.procurement.views._common import *  # noqa: F401,F403


@login_required
def sourcing_analytics(request):
    now = timezone.now()
    events = list(SourcingEvent.objects.filter(tenant=request.tenant)
                  .select_related("currency"))
    bids_by_event = {}
    for bid in (SourcingBid.objects
                .filter(tenant=request.tenant, event__in=[e.pk for e in events])
                .filter(status__in=SourcingBid.COUNTED_STATUSES)):
        bids_by_event.setdefault(bid.event_id, []).append(bid)

    awarded = [e for e in events if e.status == "awarded"]
    won_bids = {bid.event_id: bid for bids in bids_by_event.values() for bid in bids
                if bid.status == "won"}

    total_budget = Decimal("0")
    has_budget = False
    total_awarded_price = Decimal("0")
    comparable = 0  # events where budget AND award price both exist → honest savings pairs
    savings_rows = []
    cycle_days = []
    participation = []

    for event in awarded:
        won = won_bids.get(event.pk)
        counted = len(bids_by_event.get(event.pk, []))
        participation.append(counted)
        row = {"event": event, "won": won, "bids": counted,
               "budget": event.budget_estimate, "price": won.total_price if won else None,
               "savings": None, "savings_pct": None, "cycle_days": None}
        if event.awarded_at:
            row["cycle_days"] = max((event.awarded_at - event.created_at).days, 0)
            cycle_days.append(row["cycle_days"])
        if won is not None:
            total_awarded_price += won.total_price
            if event.budget_estimate is not None:
                has_budget = True
                total_budget += event.budget_estimate
                saving = event.budget_estimate - won.total_price
                row["savings"] = saving
                if event.budget_estimate > 0:
                    row["savings_pct"] = (saving / event.budget_estimate * 100).quantize(
                        Decimal("0.1"))
                comparable += 1
        savings_rows.append(row)

    def _mean(values):
        return (sum(values) / len(values)).quantize(Decimal("0.1")) if values else None

    total_savings = (total_budget - total_awarded_price) if has_budget else None

    # "Market trends" at this layer = participation over recent events: bids per month for the
    # last six months, derived from event opens (created_at when never opened).
    months = []
    month_counts = []
    for offset in range(5, -1, -1):
        start = (now - timedelta(days=30 * offset)).replace(day=1, hour=0, minute=0,
                                                            second=0, microsecond=0)
        end = ((start + timedelta(days=31)).replace(day=1) if start.month < 12
               else start.replace(year=start.year + 1, month=1, day=1))
        label = start.strftime("%b %Y")
        count = sum(1 for e in events
                    if (e.opened_at or e.created_at) and start <= (e.opened_at or e.created_at) < end)
        n_bids = sum(1 for bids in bids_by_event.values() for bid in bids
                     if start <= bid.created_at < end)
        months.append(label)
        month_counts.append({"events": count, "bids": n_bids})

    return render(request, "procurement/sourcingtendering/analytics.html", {
        "stats": {
            "n_events": len(events),
            "n_open": sum(1 for e in events if e.status == "open"),
            "n_closed": sum(1 for e in events if e.is_evaluating),
            "n_awarded": len(awarded),
            "n_cancelled": sum(1 for e in events if e.status == "cancelled"),
            "total_budget": total_budget if has_budget else None,
            "total_awarded_price": total_awarded_price if awarded else None,
            "total_savings": total_savings,
            "comparable_events": comparable,
            "avg_participation": _mean(participation),
            "avg_cycle_days": _mean(cycle_days),
        },
        "rows": savings_rows,
        "months": list(zip(months, month_counts)),
    })
