"""HRM 3.26 Request Management — DocumentFulfills forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.PersonalInformation._helpers import _ThemedForm


class DocumentFulfillForm(_ThemedForm):
    """The optional signed-letter upload captured by the document_fulfill action (admin-only). Reuses
    the shared _validate_upload helper + the onboarding-doc allowlist/size cap — no new constants."""

    output_file = forms.FileField(
        required=False,
        help_text="Optional: attach the signed letter (PDF/DOC/DOCX/JPG/PNG, max 10 MB).")

    def clean_output_file(self):
        return _validate_upload(self.cleaned_data.get("output_file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Letter")
