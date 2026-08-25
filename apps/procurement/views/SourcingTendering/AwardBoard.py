"""Procurement 6.5 Sourcing & Tendering — Award Recommendation board.

**Award Recommendation** bullet: "Automated generation of award scenarios based on total cost
and compliance." One computed page over the most recently CLOSED, not-yet-awarded events: for
each, the compliant still-live bids ranked by weighted score then price (the shared evaluation
math), with the recommended row called out and a one-click admin award that posts to
``event_award``. Nothing is stored — refresh recomputes; the DECISION is what persists.

The whole page costs ~4 queries regardless of the cap (batched in ``evaluate_events_batch``).
"""
from apps.procurement.models import SourcingEvent
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import evaluate_events_batch

#: How many closed events the board renders — a decision surface, not an export.
AWARD_BOARD_EVENT_CAP = 20


@login_required
def award_board(request):
    events = list(SourcingEvent.objects.filter(tenant=request.tenant, status="closed")
                  .select_related("currency")
                  .order_by("-closed_at", "-id")[:AWARD_BOARD_EVENT_CAP])
    scenarios = evaluate_events_batch(events)
    rows = [{
        "event": event,
        "candidates": scenarios.get(event.pk, []),
        "recommended": scenarios[event.pk][0] if scenarios.get(event.pk) else None,
    } for event in events]
    return render(request, "procurement/sourcingtendering/awards.html", {
        "rows": rows,
    })
