"""HRM 3.5 Job Requisition — REQ_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


REQ_TYPE_CHOICES = [
    ("standard", "Standard"),
    ("backfill", "Backfill"),
    ("replacement", "Replacement"),
    ("evergreen", "Evergreen / Pipeline"),
]
