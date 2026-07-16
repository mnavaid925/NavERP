"""HRM 3.29 Attendance Reports — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRecord,
)


# =============================================================================================
# 3.29 Attendance Reports (derived, read-only — NO models). Reuse the 3.28 report helpers
# (_report_period / _report_department / _dept_choices). @tenant_admin_required, tenant-scoped.
# AttendanceRecord.employee -> EmployeeProfile -> employment (aggregate via employee__employment__
# org_unit, never the .department @property). "Tracked days" excludes holiday/on_leave rows.
# =============================================================================================
_ATT_NON_WORKING = ("holiday", "on_leave")


_DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _attendance_base(tenant, date_from, date_to, dept):
    qs = AttendanceRecord.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
    if dept:
        qs = qs.filter(employee__employment__org_unit=dept)
    return qs


def _attendance_pe_tracked(counts):
    """(present_equivalent, tracked) from a {status: count} dict."""
    tracked = sum(counts.values()) - counts.get("holiday", 0) - counts.get("on_leave", 0)
    pe = counts.get("present", 0) + counts.get("regularized", 0) + 0.5 * counts.get("half_day", 0)
    return pe, tracked


def _fold_att(acc, status, count):
    """Fold one (status, count) into a `{present, tracked}` accumulator — the single source of truth
    for 'tracked excludes holiday/on_leave' + 'present-equivalent = present + regularized + ½·half_day'
    so the by-department / monthly-trend pivots can't drift from the top-level total."""
    if status not in _ATT_NON_WORKING:
        acc["tracked"] += count
    if status in ("present", "regularized"):
        acc["present"] += count
    elif status == "half_day":
        acc["present"] += 0.5 * count
