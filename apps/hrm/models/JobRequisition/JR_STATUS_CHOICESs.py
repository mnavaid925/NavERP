"""HRM 3.5 Job Requisition — JR_STATUS_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


JR_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("pending_approval", "Pending Approval"),
    ("approved", "Approved"),
    ("posted", "Posted"),
    ("on_hold", "On Hold"),
    ("filled", "Filled"),
    ("cancelled", "Cancelled"),
    ("rejected", "Rejected"),
]
