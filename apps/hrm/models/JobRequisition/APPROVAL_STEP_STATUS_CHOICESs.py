"""HRM 3.5 Job Requisition — APPROVAL_STEP_STATUS_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


APPROVAL_STEP_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("returned", "Returned for Revision"),
    ("skipped", "Skipped"),
]
