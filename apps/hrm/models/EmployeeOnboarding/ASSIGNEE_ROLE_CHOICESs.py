"""HRM 3.3 Employee Onboarding — ASSIGNEE_ROLE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


ASSIGNEE_ROLE_CHOICES = [
    ("hr", "HR"),
    ("it", "IT"),
    ("manager", "Manager"),
    ("buddy", "Buddy"),
    ("new_hire", "New Hire"),
]
