"""HRM 3.41 Employee Engagement & Wellbeing — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


def _can_manage_action_plan(request, obj):
    """A survey action plan is manageable by a tenant admin OR by its accountable owner (who is often a
    manager, not an admin). Mirrors _can_manage_own_child, keyed on ``owner`` instead of ``employee``."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and obj.owner_id == profile.pk
