"""HRM 3.8 Offer Management — PREBOARDING_DOC_TYPE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Pre-boarding document-collection catalog (HiBob/iCIMS convention). Deliberately
# distinct from the post-start 3.3 OnboardingDocument.
PREBOARDING_DOC_TYPE_CHOICES = [
    ("id_proof", "ID Proof"),
    ("address_proof", "Address Proof"),
    ("tax_form", "Tax Form"),
    ("bank_details", "Bank / Direct-Deposit Details"),
    ("nda", "NDA / Confidentiality Agreement"),
    ("education_certificate", "Education Certificate"),
    ("background_check_consent", "Background-Check Consent"),
    ("other", "Other"),
]
