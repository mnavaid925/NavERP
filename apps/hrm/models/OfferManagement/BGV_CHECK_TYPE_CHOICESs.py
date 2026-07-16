"""HRM 3.8 Offer Management — BGV_CHECK_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Typed verification categories (Checkr/HireRight standardized check types).
BGV_CHECK_TYPE_CHOICES = [
    ("criminal", "Criminal Record"),
    ("employment", "Employment History"),
    ("education", "Education Verification"),
    ("professional_license", "Professional License / Certification"),
    ("identity", "Identity Verification"),
    ("credit", "Credit Check"),
]
