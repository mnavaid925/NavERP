"""HRM 3.27 Communication Hub — ALLOWED_COMPLIANCE_DOC_EXTENSIONSs forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403


# Compliance document uploads (contracts / policies / inspection reports): documents + scans, 10 MB cap.
ALLOWED_COMPLIANCE_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
