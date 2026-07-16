"""HRM 3.16 Tax & Investment — Investmentproof forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    InvestmentProof,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class InvestmentProofForm(TenantModelForm):
    # verification_status / verified_by / verified_at / rejection_reason are workflow-owned — set only
    # by the verify/reject/on_hold POST actions, never on this upload form.
    class Meta:
        model = InvestmentProof
        fields = ["file", "title", "amount", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def clean_file(self):
        # Reuse the shared extension+size guard (docs/images, 10 MB), mirroring EmployeeDocumentForm.
        return _validate_upload(self.cleaned_data.get("file"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Proof")
