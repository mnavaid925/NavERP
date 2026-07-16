"""HRM 3.16 Tax & Investment — NEW_REGIME_ALLOWED_SECTIONSs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Sections that still reduce taxable income under the NEW regime (a static map, not a DB flag):
# only the additional-NPS 80CCD(1B) + the standard deduction survive; 80C/80D/HRA/24b/LTA/80E and
# other Chapter VI-A deductions do NOT apply under the new regime.
NEW_REGIME_ALLOWED_SECTIONS = frozenset({"80ccd_1b_nps"})
