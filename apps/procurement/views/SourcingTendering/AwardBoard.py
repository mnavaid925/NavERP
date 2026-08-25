"""Procurement 6.5 Sourcing & Tendering — Award Recommendation board.

**Award Recommendation** bullet: "Automated generation of award scenarios based on total cost
and compliance." One computed page over every CLOSED, not-yet-awarded event: for each, the
compliant still-live bids ranked by weighted score then price (the shared ``evaluate_event``
math), with the recommended row called out and a one-click admin award that posts to
``event_award``. Nothing is stored — refresh recomputes; the DECISION is what persists.
"""
from apps.procurement.models import SourcingEvent
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import evaluate_event


@login_required
def award_board(request):
    # Bounded at 20 events: each row costs two small queries inside evaluate_event (scores +
    # live bids), and a board is a decision surface, not an export. Newest-closed first.
    events = (SourcingEvent.objects.filter(tenant=request.tenant, status="closed")
              .select_related("currency", "requisition")
              .order_by("-closed_at", "-id")[:20])
    rows = []
    for event in events:
        _criteria, candidates = evaluate_event(event)
        rows.append({
            "event": event,
            "candidates": candidates,
            "recommended": candidates[0] if candidates else None,
            "n_live": len(candidates),
        })
    return render(request, "procurement/sourcingtendering/awards.html", {
        "rows": rows,
    })
