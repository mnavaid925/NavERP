"""HRM 3.3 Employee Onboarding — Document forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingDocument,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class OnboardingDocumentForm(TenantModelForm):
    # SECURITY: `esign_status` and `signed_at` are excluded — both are workflow-owned. The model's
    # save() derives the open esign_status from `esign_required` (not_required ↔ pending), and the
    # mark-signed action advances pending → signed (stamping signed_at + an audit row). Exposing
    # esign_status here would let any user self-sign a document via a crafted POST, with no audit.
    class Meta:
        model = OnboardingDocument
        fields = ["program", "document_type", "title", "description", "file", "esign_required",
                  "due_date", "external_ref"]

    def clean_file(self):
        # WARNING: extension allowlist only (a renamed file passes). Keep MEDIA_ROOT outside the web
        # root (README) and serve uploads with Content-Disposition: attachment +
        # X-Content-Type-Options: nosniff. Add MIME sniffing (python-magic) when that dep lands.
        return _validate_upload(self.cleaned_data.get("file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="File")
