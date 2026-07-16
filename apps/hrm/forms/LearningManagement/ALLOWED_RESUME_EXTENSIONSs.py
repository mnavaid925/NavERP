"""HRM 3.23 Learning Management (LMS) — ALLOWED_RESUME_EXTENSIONSs forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403


# Resume / cover-letter upload safety (3.6): documents only (no images) + 10 MB cap.
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
