"""HRM 3.6 Candidate Management — SKILL_PROFICIENCY_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


SKILL_PROFICIENCY_CHOICES = [
    ("beginner", "Beginner"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced"),
    ("expert", "Expert"),
]
