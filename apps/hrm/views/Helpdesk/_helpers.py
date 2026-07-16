"""HRM 3.36 Helpdesk — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child


# ---- Helpdesk tickets -------------------------------------------------------------------------
def _ticket_is_agent(request, obj):
    """A ticket 'agent' = a tenant admin or the ticket's current assignee."""
    return _is_admin(request.user) or (obj.assignee_id is not None and obj.assignee_id == request.user.id)


def _ticket_can_view(request, obj):
    """The requester (own), an admin, or the assignee may view a ticket."""
    return _can_manage_own_child(request, obj) or _ticket_is_agent(request, obj)


def _ticket_mark_first_response(obj):
    """Stamp first_responded_at on the first agent touch (start/waiting/resolve) if not already set."""
    if obj.first_responded_at is None:
        obj.first_responded_at = timezone.now()
