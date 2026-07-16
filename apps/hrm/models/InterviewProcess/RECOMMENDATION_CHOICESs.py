"""HRM 3.7 Interview Process — RECOMMENDATION_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# 5-level hire signal (Greenhouse/Zoho convention: Strong No … Strong Yes).
RECOMMENDATION_CHOICES = [
    ("strong_no", "Strong No"),
    ("no", "No"),
    ("maybe", "Maybe"),
    ("yes", "Yes"),
    ("strong_yes", "Strong Yes"),
]
