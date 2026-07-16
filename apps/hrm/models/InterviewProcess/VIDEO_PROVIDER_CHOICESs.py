"""HRM 3.7 Interview Process — VIDEO_PROVIDER_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


VIDEO_PROVIDER_CHOICES = [
    ("zoom", "Zoom"),
    ("teams", "Microsoft Teams"),
    ("google_meet", "Google Meet"),
    ("other", "Other"),
]
