"""HRM 3.23 Learning Management (LMS) — Learningcontentitem forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningContentItem,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.LearningManagement.ALLOWED_SCORM_EXTENSIONSs import ALLOWED_SCORM_EXTENSIONS
from apps.hrm.forms.LearningManagement.MAX_SCORM_BYTESs import MAX_SCORM_BYTES


# ----------------------------------------------------------------------- 3.23 Learning Management (LMS)
class LearningContentItemForm(TenantModelForm):
    # `course` is set from the URL in the nested create view (mirrors PIPCheckInForm excluding `pip`).
    class Meta:
        model = LearningContentItem
        fields = ["title", "description", "content_type", "sequence", "is_required",
                  "estimated_duration_minutes", "video_url", "document_file", "scorm_package",
                  "external_url", "body_text", "pass_threshold_percent", "max_attempts", "time_limit_minutes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "body_text": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
        }

    def clean_document_file(self):
        # WARNING: extension allowlist only — keep MEDIA_ROOT outside the web root and serve with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff in production (mirrors the
        # onboarding-doc upload forms; MEDIA hardening is a tracked README TODO). _validate_upload
        # enforces the extension on name alone, preserving this method's original name-only guard.
        return _validate_upload(self.cleaned_data.get("document_file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Document")

    def clean_scorm_package(self):
        # WARNING: stored as an opaque file only — never extracted this pass. A future SCORM-extraction
        # handler MUST guard against zip-slip / path traversal before writing extracted files to disk.
        # Also (as for every upload here) keep MEDIA_ROOT outside the web root + serve with
        # Content-Disposition: attachment + X-Content-Type-Options: nosniff in production.
        return _validate_upload(self.cleaned_data.get("scorm_package"),
                                allowed_ext=ALLOWED_SCORM_EXTENSIONS,
                                max_bytes=MAX_SCORM_BYTES, label="SCORM package")
