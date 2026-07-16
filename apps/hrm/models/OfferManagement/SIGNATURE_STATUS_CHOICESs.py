"""HRM 3.8 Offer Management — SIGNATURE_STATUS_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# E-signature status — field only this pass; live DocuSign/Adobe/Zoho Sign wiring deferred.
SIGNATURE_STATUS_CHOICES = [
    ("not_sent", "Not Sent"),
    ("sent", "Sent for Signature"),
    ("viewed", "Viewed by Candidate"),
    ("signed", "Signed"),
    ("declined", "Declined to Sign"),
]
