"""HRM 3.27 Communication Hub — EmploymentContracts forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    EmploymentContract,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.CommunicationHub.ALLOWED_COMPLIANCE_DOC_EXTENSIONSs import ALLOWED_COMPLIANCE_DOC_EXTENSIONS
from apps.hrm.forms.CommunicationHub.MAX_COMPLIANCE_DOC_BYTESs import MAX_COMPLIANCE_DOC_BYTES


class EmploymentContractForm(TenantModelForm):
    class Meta:
        model = EmploymentContract
        fields = ["employee", "contract_type", "start_date", "end_date", "probation_end_date",
                  "notice_period_days", "designation", "salary_structure", "status", "renewed_from",
                  "document", "signed_on", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))
            if "designation" in self.fields:
                self.fields["designation"].queryset = (
                    Designation.objects.filter(tenant=self.tenant).order_by("name"))
            if "renewed_from" in self.fields:
                qs = EmploymentContract.objects.filter(tenant=self.tenant)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)  # a contract can't renew itself
                self.fields["renewed_from"].queryset = qs.order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        probation = cleaned.get("probation_end_date")
        if start and probation and probation < start:
            self.add_error("probation_end_date", "Probation end cannot be before the start date.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
                                max_bytes=MAX_COMPLIANCE_DOC_BYTES, label="Contract Document")
