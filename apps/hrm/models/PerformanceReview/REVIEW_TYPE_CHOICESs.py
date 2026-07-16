"""HRM 3.19 Performance Review — REVIEW_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Shared across ReviewTemplate + PerformanceReview (a review instance denormalizes
# review_type from its template for query convenience).
REVIEW_TYPE_CHOICES = [
    ("self", "Self"),
    ("manager", "Manager"),
    ("peer", "Peer"),
    ("upward", "Upward"),
    ("skip_level", "Skip-Level"),
]
