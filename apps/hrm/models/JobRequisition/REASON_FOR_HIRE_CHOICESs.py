"""HRM 3.5 Job Requisition — REASON_FOR_HIRE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


REASON_FOR_HIRE_CHOICES = [
    ("new_headcount", "New Headcount"),
    ("backfill", "Backfill Vacancy"),
    ("replacement", "Replacement"),
    ("project", "Project / Fixed Term"),
    ("contractor_to_perm", "Contractor to Permanent"),
]
