"""HRM 3.23 Learning Management (LMS) — ALLOWED_OFFER_DOC_EXTENSIONSs forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403


# 3.8 offer/background-check/pre-boarding upload safety: signed offers + vendor reports are
# documents only; pre-boarding docs also allow ID-proof photos. 10 MB cap (mirrors onboarding docs).
ALLOWED_OFFER_DOC_EXTENSIONS = {".pdf", ".doc", ".docx"}
