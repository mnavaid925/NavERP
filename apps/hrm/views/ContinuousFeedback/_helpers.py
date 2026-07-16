"""HRM 3.20 Continuous Feedback — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# =========================================================================
# 3.20 Continuous Feedback (Performance Management) — real-time feedback + 1:1
# meetings + a computed feedback dashboard. Reuses _current_employee_profile /
# _is_admin from the 3.19 section (never redefined). Confidentiality clones 3.19
# field-for-field: OneOnOneMeeting.manager_private_notes is manager-only (never
# rendered employee-side, and the edit form that holds it is manager/admin-gated,
# per L20), and an anonymous Feedback masks its giver on read for non-admin/
# non-giver viewers.
# =========================================================================
def _can_view_feedback(request, feedback):
    """Who may view a Feedback row: a tenant admin, the giver, or the receiver — plus ANY employee
    for a public-feed row (giver still masked if anonymous), or a team-mate sharing the receiver's
    org unit for a team-visibility row. Private rows are otherwise confidential (mirrors
    _can_view_review)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    if profile is not None and profile.pk in (feedback.giver_id, feedback.receiver_id):
        return True
    if feedback.visibility == "public":
        return True
    if feedback.visibility == "team" and profile is not None and profile.employment_id:
        recv = feedback.receiver
        recv_org = recv.employment.org_unit_id if recv.employment_id else None
        return recv_org is not None and recv_org == profile.employment.org_unit_id
    return False


def _visible_feedback_q(request):
    """A ``Q`` restricting feedback lists to what the requester may see: public rows OR their own
    given/received rows OR team-visible rows sharing the receiver's org unit. ``None`` for a tenant
    admin (no restriction) — same contract as _visible_reviews_q."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(visibility="public")  # a tenant-less/employee-less user sees only the public feed
    cond = Q(visibility="public") | Q(giver=profile) | Q(receiver=profile)
    org_id = profile.employment.org_unit_id if profile.employment_id else None
    if org_id is not None:
        cond |= Q(visibility="team", receiver__employment__org_unit_id=org_id)
    return cond


def _can_edit_feedback(request, feedback):
    """A Feedback row is editable ONLY by the giver (never the receiver) or a tenant admin, and only
    while it is still open (content locks once acknowledged, or once a request has been responded to)
    — mirrors _can_edit_review's status-lock-plus-author-check shape."""
    if feedback.status in ("acknowledged", "responded"):
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == feedback.giver_id


def _feedback_giver_display(request, feedback):
    """The giver name to render — 'Anonymous' for a non-admin/non-giver viewer of an anonymous row,
    else the real party name (or '—' when the giver FK is null)."""
    profile = _current_employee_profile(request)
    is_giver = profile is not None and profile.pk == feedback.giver_id
    if feedback.giver_anonymized and not (_is_admin(request.user) or is_giver):
        return "Anonymous"
    return feedback.giver.party.name if feedback.giver_id else "—"


def _can_view_meeting(request, meeting):
    """A 1:1 is inherently two-party — only its manager, its employee, or a tenant admin may view it."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (meeting.manager_id, meeting.employee_id)


def _visible_meetings_q(request):
    """A ``Q`` restricting the 1:1 list to the requester's own meetings (as manager or employee).
    ``None`` for a tenant admin (no restriction)."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(manager=profile) | Q(employee=profile)


def _can_manage_meeting(request, meeting):
    """Manager-or-admin — for the complete/cancel/edit actions and the private-notes read gate. The
    employee side collaborates via action items + the shared read view but never reaches the edit
    form (which holds manager_private_notes)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == meeting.manager_id


def _can_manage_action_item(request, item):
    """Edit/delete/toggle an action item: an admin, or a MEETING PARTICIPANT (per _can_view_meeting)
    who is the item's owner or the meeting's manager. Requiring meeting access — not owner_id alone —
    closes the gap where an item assigned to an outsider would grant them mutate rights on a 1:1 they
    can't even view (edit rights must never be broader than view rights)."""
    if _is_admin(request.user):
        return True
    if not _can_view_meeting(request, item.meeting):
        return False
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (item.owner_id, item.meeting.manager_id)
