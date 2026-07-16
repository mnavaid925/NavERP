"""HRM 3.35 Travel Management — _helpers models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.35 Travel Management — TravelPolicy / TravelRequest / TravelBooking
#
# Corporate travel: a per-grade policy master, a trip request with a single-approver workflow
# (reuses the _hr_request_* helpers verbatim) + a travel advance, and inline bookings. Post-travel
# settlement REUSES 3.34's ExpenseClaim (a "Generate Settlement" action creates a linked claim).
# out_of_policy is a computed soft-flag (never stored). No GL/payroll posting.
# ---------------------------------------------------------------------------
_TRAVEL_CLASS_RANK = {"economy": 0, "premium_economy": 1, "business": 2, "first": 3}
