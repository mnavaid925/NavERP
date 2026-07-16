"""HRM 3.23 Learning Management (LMS) — ALLOWED_SCORM_EXTENSIONSs forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403


# 3.23 LMS SCORM package upload safety: a zipped package only + a 50 MB cap.
ALLOWED_SCORM_EXTENSIONS = {".zip"}
