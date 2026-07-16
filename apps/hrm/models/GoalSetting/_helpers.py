"""HRM 3.18 Goal Setting — _helpers models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ===========================================================================
# 3.18 Goal Setting — Performance Management (OKR mechanics)
# ---------------------------------------------------------------------------
# The first Performance-Management sub-module (3.18 → 3.19 Performance Review →
# 3.20 Continuous Feedback → 3.21 Performance Improvement). Pure HRM-domain
# extension hanging off ``EmployeeProfile`` (the goal owner) and ``core.OrgUnit``
# (department scope, reused exactly as ``Designation.department`` does) — NO new
# core-spine entity. Progress % and health are DERIVED (never stored editable
# columns), mirroring how ``LeaveAllocation``/``AttendanceRecord.hours_worked``
# already work. Cascading alignment is the single self-FK ``Objective.parent_objective``
# (vertical only); weighting is KR-level (``KeyResult.weight``); the KR-type
# distinction is a ``metric_type`` CharField choice rather than a 5th model.
# ===========================================================================
def _clamp_pct(value):
    """Clamp a Decimal progress percentage into ``[0, 100]``."""
    if value < ZERO:
        return ZERO
    hundred = Decimal("100")
    return hundred if value > hundred else value


def _pace_health(progress_pct, start_date, end_date, *, completed=False):
    """Derive an on_track/at_risk/off_track health signal by comparing realized
    progress against the fraction of the period's time already elapsed. Shared by
    ``Objective.health_status`` and ``KeyResult.health_status`` (3.18.5 status/health
    coloring — Weekdone/WorkBoard/Betterworks). ``completed`` short-circuits to the
    terminal state. Guards a zero-length period (no divide-by-zero)."""
    if completed:
        return "completed"
    if not start_date or not end_date:
        return "on_track"
    total_days = (end_date - start_date).days
    if total_days <= 0:
        expected = Decimal("100")
    else:
        elapsed = min(max((timezone.localdate() - start_date).days, 0), total_days)
        expected = Decimal(elapsed) / Decimal(total_days) * Decimal("100")
    gap = expected - Decimal(progress_pct)  # positive ⇒ behind the expected pace
    if gap <= 10:
        return "on_track"
    if gap <= 25:
        return "at_risk"
    return "off_track"


# Human labels for the derived health_status codes (no choices= field to give a get_*_display).
_HEALTH_LABELS = {"on_track": "On Track", "at_risk": "At Risk",
                  "off_track": "Off Track", "completed": "Completed"}
