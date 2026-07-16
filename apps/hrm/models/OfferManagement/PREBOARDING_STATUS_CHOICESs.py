"""HRM 3.8 Offer Management — PREBOARDING_STATUS_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Per-item collection status (mirrors OnboardingTask/ClearanceItem status-child convention).
PREBOARDING_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("submitted", "Submitted"),
    ("verified", "Verified"),
    ("rejected", "Rejected"),
]
