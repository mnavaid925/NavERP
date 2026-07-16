"""HRM 3.6 Candidate Management — DELIVERY_STATUS_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


DELIVERY_STATUS_CHOICES = [
    ("sent", "Sent"),
    ("delivered", "Delivered"),
    ("failed", "Failed"),
    ("pending", "Pending"),
]
