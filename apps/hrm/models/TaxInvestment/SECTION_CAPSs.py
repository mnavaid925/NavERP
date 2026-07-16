"""HRM 3.16 Tax & Investment — SECTION_CAPSs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Statutory per-section deduction caps (FY 2025-26). Applied (capped + surfaced via capped_sections),
# never silently truncated on the declaration line itself, so the employee's raw claim is preserved.
SECTION_CAPS = {
    "80c": Decimal("150000.00"),
    "80ccd_1b_nps": Decimal("50000.00"),
    "24b_home_loan_interest": Decimal("200000.00"),
}
