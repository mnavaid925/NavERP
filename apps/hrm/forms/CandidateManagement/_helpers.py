"""HRM 3.6 Candidate Management — _helpers forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.forms.LearningManagement.ALLOWED_RESUME_EXTENSIONSs import ALLOWED_RESUME_EXTENSIONS
from apps.hrm.forms.LearningManagement.MAX_RESUME_BYTESs import MAX_RESUME_BYTES


def _validate_resume(f):
    """Shared resume/cover-letter upload guard — documents only (PDF/DOC/DOCX), 10 MB cap.
    Validates a freshly-uploaded file only (an existing FieldFile has no new size to re-check)."""
    return _validate_upload(f, allowed_ext=ALLOWED_RESUME_EXTENSIONS, max_bytes=MAX_RESUME_BYTES)


def _validate_upload(f, *, allowed_ext, max_bytes, label="File"):
    """Generic upload guard — extension allowlist + size cap. Validates a freshly-uploaded file only
    (an existing FieldFile has no new size to re-check). The extension is enforced whenever the upload
    exposes a name; the size cap applies only when a size attribute is present (some file-like wrappers
    omit it), so a name-only upload is still extension-checked rather than skipped."""
    if f and hasattr(f, "name"):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in allowed_ext:
            raise forms.ValidationError(
                f"{label} type '{ext}' is not allowed. Use {', '.join(sorted(allowed_ext))}.")
        if hasattr(f, "size") and f.size and f.size > max_bytes:
            raise forms.ValidationError(f"{label} exceeds the {max_bytes // (1024 * 1024)} MB limit.")
        # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve uploads with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff (mirrors onboarding docs).
    return f
