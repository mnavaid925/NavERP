"""HRM 3.2 Organizational Structure — EmployeeDocuments forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeDocument,
    EmployeeProfile,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class EmployeeDocumentForm(TenantModelForm):
    # SECURITY: `verification_status`, `verified_by`, `verified_at` are excluded — set only by the
    # mark-verified / reject workflow actions (which stamp who/when + an audit row). Exposing them
    # would let any user self-verify a document via a crafted POST.
    class Meta:
        model = EmployeeDocument
        fields = ["employee", "document_type", "title", "document_number", "issuing_authority",
                  "issuing_country", "issued_on", "expires_on", "is_confidential", "file", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["employee"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))

    def clean_file(self):
        return _validate_upload(self.cleaned_data.get("file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="File")
