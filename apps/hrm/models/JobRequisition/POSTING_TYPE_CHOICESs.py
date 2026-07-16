"""HRM 3.5 Job Requisition — POSTING_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


POSTING_TYPE_CHOICES = [
    ("internal", "Internal Only"),
    ("external", "External Only"),
    ("both", "Internal & External"),
]
