"""HRM 3.8 Offer Management — BGV_RESULT_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


BGV_RESULT_CHOICES = [
    ("clear", "Clear"),
    ("consider", "Consider"),
    ("not_applicable", "Not Applicable"),
]
