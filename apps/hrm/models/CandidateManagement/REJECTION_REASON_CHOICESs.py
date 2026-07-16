"""HRM 3.6 Candidate Management — REJECTION_REASON_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


REJECTION_REASON_CHOICES = [
    ("overqualified", "Overqualified"),
    ("underqualified", "Underqualified"),
    ("position_filled", "Position Filled"),
    ("no_response", "No Response / Unresponsive"),
    ("failed_screening", "Failed Screening"),
    ("other", "Other"),
]
