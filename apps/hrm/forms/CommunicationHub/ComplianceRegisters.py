"""HRM 3.27 Communication Hub — ComplianceRegisters forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ComplianceRegister,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.CommunicationHub.ALLOWED_COMPLIANCE_DOC_EXTENSIONSs import ALLOWED_COMPLIANCE_DOC_EXTENSIONS
from apps.hrm.forms.CommunicationHub.MAX_COMPLIANCE_DOC_BYTESs import MAX_COMPLIANCE_DOC_BYTES


class ComplianceRegisterForm(TenantModelForm):
    class Meta:
        model = ComplianceRegister
        fields = ["register_type", "title", "jurisdiction", "authority", "period_start", "period_end",
                  "due_date", "status", "filed_on", "inspector_name", "findings", "document", "notes"]
        widgets = {"findings": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end cannot be before the period start.")
        if cleaned.get("status") == "filed" and not cleaned.get("filed_on"):
            self.add_error("filed_on", "A filed record needs a filing date.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
                                max_bytes=MAX_COMPLIANCE_DOC_BYTES, label="Compliance Document")
