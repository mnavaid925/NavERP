"""HRM 3.7 Interview Process — PANELIST_ROLE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


PANELIST_ROLE_CHOICES = [
    ("lead", "Lead Interviewer"),
    ("interviewer", "Interviewer"),
    ("shadow", "Shadow / Trainee"),
    ("observer", "Observer"),
]
