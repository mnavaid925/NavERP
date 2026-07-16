"""HRM 3.8 Offer Management — BGV_MANUAL_TRANSITION_STATUSESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Intermediate statuses a manual "update status" action can move an initiated check to (the deferred
# vendor webhook would write these too). Shared by the view guard and the detail-page dropdown so the two
# never drift.
BGV_MANUAL_TRANSITION_STATUSES = ("in_progress", "action_needed", "ready_for_review")
