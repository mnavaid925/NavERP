"""HRM 3.6 Candidate Management — SKILL_SOURCE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


SKILL_SOURCE_CHOICES = [
    ("parsed", "Resume Parsed"),
    ("manual", "Manually Added"),
    ("self_reported", "Self-Reported"),
]
