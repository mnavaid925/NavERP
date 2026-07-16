"""HRM 3.10 Leave Management — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


# ============================================================ Leave Policy engine (3.10)
def _policy_year(request):
    """Resolve the ?year / POSTed year param to an int, defaulting to the current year. Bounded to
    a sane window so an oversized all-digit string can't overflow PositiveSmallIntegerField and raise
    an unhandled DB error/500 (security-review: DoS / stack-trace leak if DEBUG)."""
    raw = (request.POST.get("year") or request.GET.get("year") or "").strip()
    if raw.isdigit():
        year = int(raw)
        if 2000 <= year <= 2100:
            return year
    return timezone.localdate().year


def _accrual_target(leave_type, year, current_year, current_month):
    """Days accrued for a leave type by ``year``: annual → the full grant; monthly → the per-month
    rate × elapsed months (12 for a past year, the current month for the current year)."""
    rate = leave_type.accrual_days or Decimal("0")
    if leave_type.accrual_rule == "annual":
        return rate
    if leave_type.accrual_rule == "monthly":
        if year > current_year:
            months = 0          # nothing has accrued yet for a future year
        elif year < current_year:
            months = 12         # a past year has fully accrued
        else:
            months = current_month
        return rate * Decimal(months)
    return Decimal("0")  # "none"
