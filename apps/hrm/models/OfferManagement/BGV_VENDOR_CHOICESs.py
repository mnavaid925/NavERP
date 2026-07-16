"""HRM 3.8 Offer Management — BGV_VENDOR_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Background-verification vendor marketplace (Checkr/HireRight/Sterling convention) — field only.
BGV_VENDOR_CHOICES = [
    ("checkr", "Checkr"),
    ("hireright", "HireRight"),
    ("sterling", "Sterling"),
    ("other", "Other / In-house"),
]
