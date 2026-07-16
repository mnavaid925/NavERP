"""HRM 3.5 Job Requisition — APPROVER_ROLE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


APPROVER_ROLE_CHOICES = [
    ("hiring_manager", "Hiring Manager"),
    ("hr", "HR"),
    ("finance", "Finance"),
    ("executive", "Executive"),
    ("custom", "Custom"),
]
