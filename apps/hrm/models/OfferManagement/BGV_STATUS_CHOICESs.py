"""HRM 3.8 Offer Management — BGV_STATUS_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Standardized check lifecycle (Checkr/Sterling: Started → In Progress → Action
# Needed → Ready for Review → Completed). ``result`` (below) is the separate
# overall verdict, orthogonal to the workflow status.
BGV_STATUS_CHOICES = [
    ("not_started", "Not Started"),
    ("consent_pending", "Consent Pending"),
    ("initiated", "Initiated"),
    ("in_progress", "In Progress"),
    ("action_needed", "Action Needed"),
    ("ready_for_review", "Ready for Review"),
    ("completed", "Completed"),
]
