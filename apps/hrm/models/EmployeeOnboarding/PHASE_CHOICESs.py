"""HRM 3.3 Employee Onboarding — PHASE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


PHASE_CHOICES = [
    ("preboarding", "Preboarding"),
    ("week_1", "Week 1"),
    ("month_1", "Month 1"),
    ("month_2", "Month 2"),
    ("month_3", "Month 3"),
    ("ongoing", "Ongoing"),
]
