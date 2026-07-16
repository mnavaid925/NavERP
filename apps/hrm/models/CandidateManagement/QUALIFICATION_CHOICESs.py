"""HRM 3.6 Candidate Management — QUALIFICATION_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


QUALIFICATION_CHOICES = [
    ("high_school", "High School / Secondary"),
    ("diploma", "Diploma / Certificate"),
    ("bachelors", "Bachelor's Degree"),
    ("masters", "Master's Degree"),
    ("phd", "PhD / Doctorate"),
    ("other", "Other"),
]
