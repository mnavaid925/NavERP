"""HRM 3.19 Performance Review — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile


# ============================================================ 3.19 Performance Review (Performance Mgmt)
def _is_admin(user):
    """Tenant-admin-or-superuser check (mirrors apps.core.decorators.tenant_admin_required)."""
    return user.is_superuser or getattr(user, "is_tenant_admin", False)


def _is_reviewer(request, review):
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == review.reviewer_id


def _can_edit_review(request, review):
    """A review (and its competency ratings) is editable ONLY by the reviewer or a tenant admin,
    and ONLY while it's still a draft. This protects the manager ``private_notes`` confidentiality
    boundary (the subject must never reach the edit form to read them) and the submit→share→
    acknowledge audit trail (content is locked once submitted)."""
    return review.status == "draft" and (_is_admin(request.user) or _is_reviewer(request, review))


def _can_view_review(request, review):
    """Who may view a review's content: a tenant admin, the reviewer (their authored review), or
    the subject. Everyone else is denied — performance reviews are CONFIDENTIAL, not company-open
    the way 3.18 OKRs are (a curious employee must not read who is rated what across the tenant)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (review.subject_id, review.reviewer_id)


def _visible_reviews_q(request):
    """A ``Q`` restricting review rosters/lists to what the requester may see (their own subject or
    reviewer rows). Returns ``None`` for a tenant admin (no restriction)."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])  # a tenant-less / employee-less user sees nothing
    return Q(subject=profile) | Q(reviewer=profile)
