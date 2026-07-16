"""HRM 3.27 Communication Hub — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


# ---- Celebrations (Birthday/Anniversary — derived, no model) --------------------------------
def _next_occurrence(d, today):
    """The next date on/after `today` that lands on d's month/day (Feb-29 falls back to Mar-1)."""
    for year in (today.year, today.year + 1):
        try:
            candidate = _date(year, d.month, d.day)
        except ValueError:  # Feb 29 in a non-leap year
            candidate = _date(year, 3, 1)
        if candidate >= today:
            return candidate
    return today


def _days_until(d, today):
    return (_next_occurrence(d, today) - today).days


def _is_number(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


# ---- Announcements --------------------------------------------------------------------------
def _announcement_targets(request, obj):
    """Is this published announcement targeted at the viewer? all → everyone; department/designation →
    the viewer's own department/designation only (a viewer with no profile matches only `all`)."""
    if obj.audience_type == "all":
        return True
    profile = _current_employee_profile(request)
    if profile is None:
        return False
    if obj.audience_type == "department":
        dept_id = profile.employment.org_unit_id if profile.employment_id else None
        return dept_id is not None and obj.target_department_id == dept_id
    if obj.audience_type == "designation":
        return profile.designation_id is not None and obj.target_designation_id == profile.designation_id
    return False
