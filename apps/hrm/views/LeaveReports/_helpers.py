"""HRM 3.30 Leave Reports — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveAllocation,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _used_days_subquery


# =============================================================================================
# 3.30 Leave Reports (derived, read-only — NO models). LeaveAllocation.used_days/balance are
# derived; annotate via _used_days_subquery() (one SQL pass, no per-row @property N+1). Comp-off
# has no dedicated model: "earned" = OvertimeRequest(payout_method="comp_leave"), "availed" = leave
# against a comp-off LeaveType (name/code icontains "comp") — with an empty-state when none exist.
# =============================================================================================
def _report_year(request):
    y = (request.GET.get("year") or "").strip()
    # isdecimal()+cap: isdigit() accepts Unicode superscripts ("²") that int() would ValueError on.
    return int(y) if y.isdecimal() and len(y) <= 4 else timezone.localdate().year


def _leave_years(tenant, year):
    years = (LeaveAllocation.objects.filter(tenant=tenant)
             .order_by().values_list("year", flat=True).distinct())  # SELECT DISTINCT, no join
    return sorted(set(years) | {year}, reverse=True)


def _annotated_allocations(tenant, year):
    # Annotate used-days once (the correlated subquery); balance is derived in Python from used_db at the
    # call sites — annotating balance_db too would re-inline the whole subquery a 2nd time per row. Drop the
    # inherited Meta ordering (an unused DB join+sort — callers re-sort or just aggregate).
    return (LeaveAllocation.objects.filter(tenant=tenant, year=year)
            .annotate(used_db=_used_days_subquery())
            .select_related("employee__party", "leave_type", "employee__employment__org_unit")
            .order_by())


def _alloc_balance(a):
    return (a.allocated_days or Decimal("0")) - (a.used_db or Decimal("0")) - (a.encashed_days or Decimal("0"))
