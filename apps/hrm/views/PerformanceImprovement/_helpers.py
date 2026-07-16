"""HRM 3.21 Performance Improvement — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# =========================================================================
# 3.21 Performance Improvement (Performance Management) — PIPs + progressive
# warning letters + manager-only coaching notes. The 4th/FINAL Performance-
# Management sub-module. Reuses _current_employee_profile / _is_admin from the
# 3.19 section. CONFIDENTIALITY is the crux: PIPs/warnings are subject-or-
# issuer-or-admin only (no team/public tier); CoachingNote is coach/admin ONLY
# — the coached employee is NEVER a viewer (the strictest gate in the cluster).
# =========================================================================
def _can_view_pip(request, pip):
    """A PIP is confidential — visible only to the subject, the owning manager, or a tenant admin
    (mirrors _can_view_review; NO team/public tier)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (pip.subject_id, pip.manager_id)


def _visible_pips_q(request):
    """A ``Q`` restricting PIP lists to the subject's or manager's own rows. ``None`` for a tenant admin."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(subject=profile) | Q(manager=profile)


def _can_edit_pip(request, pip):
    """A PIP's content is editable ONLY by the manager or a tenant admin, and ONLY while it's a draft
    (locks once submitted for HR approval — protects the acknowledge/HR-approval audit trail). The
    subject is NEVER an editor (mirrors _can_edit_review)."""
    if pip.status != "draft":
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == pip.manager_id


def _can_view_warning(request, letter):
    """Visible only to the recipient, the issuer, or a tenant admin (subject-or-issuer-or-admin)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (letter.issued_to_id, letter.issued_by_id)


def _visible_warnings_q(request):
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(issued_to=profile) | Q(issued_by=profile)


def _can_edit_warning(request, letter):
    """Editable only by the issuer or admin, only while draft (locks once issued). The recipient is
    never an editor."""
    if letter.status != "draft":
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == letter.issued_by_id


def _can_view_coaching(request, note):
    """THE STRICTEST GATE: a coaching note is visible ONLY to its coach (author) or a tenant admin —
    the coached ``employee`` is EXCLUDED at every stage (clones OneOnOneMeeting.manager_private_notes at
    the whole-model level)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == note.coach_id


def _visible_coaching_q(request):
    """A ``Q`` restricting coaching notes to the coach's own rows — the ``employee`` leg is DELIBERATELY
    omitted (the subject must never see notes about themselves). ``None`` for a tenant admin."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(coach=profile)


def _can_edit_coaching(request, note):
    """Coach-or-admin only (edit rights never broader than view rights — the _can_manage_action_item
    lesson from 3.20)."""
    return _can_view_coaching(request, note)


def _can_edit_checkin(request, checkin):
    """Edit/delete a PIP check-in: the plan's manager or a tenant admin ONLY (the subject may LOG
    check-ins to self-report, but must never rewrite/delete the manager's entries — the check-in
    trail is the disciplinary record the outcome rests on), and only while the plan isn't closed."""
    pip = checkin.pip
    if pip.status == "closed":
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == pip.manager_id
