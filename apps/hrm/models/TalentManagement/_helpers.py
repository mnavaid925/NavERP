"""HRM 3.38 Talent Management & Succession — _helpers models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.38 Talent Management & Succession Planning — the HiPo/9-box + succession-bench
# layer built ON the 3.19 PerformanceReview ratings (potential_rating IS the 9-box
# potential axis; effective_rating is the performance axis) and the 3.2 Designation
# catalog. Two of the six NavERP.md bullets need NO new table: **Talent Reviews**
# reuses the 3.19 calibration board, and **Internal Mobility** reuses
# JobRequisition(posting_type="internal") + JobApplication (3.5/3.6). **Career
# Pathing** is DEFERRED (needs a CareerPath + EmployeeSkill taxonomy of its own).
#
# CONFIDENTIAL: HiPo membership, 9-box placement, flight risk and succession benches
# are HR-only data (the 3.21 PIP/CoachingNote precedent) — every 3.38 view is
# @tenant_admin_required. An employee must never see that they are (or aren't) on a
# bench or flagged a flight risk.
# ---------------------------------------------------------------------------
def _rating_band(value):
    """Band a 1-5 rating into the 9-box axis: low (<3), medium (<4), high (>=4). None passes through."""
    if value is None:
        return None
    if value < 3:
        return "low"
    if value < 4:
        return "medium"
    return "high"


# The standard 9-box labels, keyed (performance_band, potential_band).
_NINE_BOX_LABELS = {
    ("high", "high"): "Star",
    ("high", "medium"): "High Performer",
    ("high", "low"): "Solid Performer",
    ("medium", "high"): "Emerging Star",
    ("medium", "medium"): "Core Player",
    ("medium", "low"): "Average Performer",
    ("low", "high"): "Enigma",
    ("low", "medium"): "Inconsistent Player",
    ("low", "low"): "Underperformer",
}
