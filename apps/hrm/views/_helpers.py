"""Cross-cutting private helpers for the HRM views package (used by >1 sub-module)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveRequest,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


_DEC = DecimalField(max_digits=7, decimal_places=2)


def _parse_iso_date(value):
    """Return a date for a ``YYYY-MM-DD`` string, or None for blank/malformed input."""
    try:
        return _date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _used_days_subquery():
    """Correlated sub-select of approved leave-days for a LeaveAllocation's
    (tenant, employee, leave_type, start-year) window — pushes the per-row aggregate the
    ``LeaveAllocation.used_days`` property would otherwise run into one SQL pass."""
    inner = (LeaveRequest.objects
             .filter(tenant=OuterRef("tenant"), employee=OuterRef("employee"),
                     leave_type=OuterRef("leave_type"), status="approved",
                     start_date__year=OuterRef("year"))
             .values("employee").annotate(s=Sum("days")).values("s"))
    return Coalesce(Subquery(inner, output_field=_DEC), Decimal("0"), output_field=_DEC)
