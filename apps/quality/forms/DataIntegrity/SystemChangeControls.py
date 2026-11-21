from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.DataIntegrity.SystemChangeControls import SystemChangeControl
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation

User = get_user_model()


class SystemChangeControlForm(TenantModelForm):
    class Meta:
        model = SystemChangeControl
        fields = [
            "title",
            "system",
            "change_type",
            "change_priority",
            "gxp_impact",
            "requestor",
            "system_owner",
            "qa_lead",
            "org_unit",
            "description",
            "business_justification",
            "data_integrity_risk",
            "validation_deliverables",
            "rollback_plan",
            "target_date",
            "post_review_due_date",
            "status",
            "testing_successful",
            "data_backup_verified",
            "ccb_approved",
            "closure_summary",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ERP Quality Module Database Schema Migration & Audit Log Hardening"}),
            "system": forms.Select(attrs={"class": "form-select"}),
            "change_type": forms.Select(attrs={"class": "form-select"}),
            "change_priority": forms.Select(attrs={"class": "form-select"}),
            "gxp_impact": forms.Select(attrs={"class": "form-select"}),
            "requestor": forms.Select(attrs={"class": "form-select"}),
            "system_owner": forms.Select(attrs={"class": "form-select"}),
            "qa_lead": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Technical description of the proposed hardware, software, cloud or configuration change..."}),
            "business_justification": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Regulatory or operational driver for the change..."}),
            "data_integrity_risk": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Potential impact on ALCOA+ data integrity, audit trails, or electronic records..."}),
            "validation_deliverables": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Required test scripts, qualification protocols, user training, and UAT evidence..."}),
            "rollback_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Backout instructions in case of deployment exception or unexpected failure..."}),
            "target_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "post_review_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "testing_successful": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "data_backup_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "ccb_approved": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "closure_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Final implementation outcome and QA release notes..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["system"].queryset = ComputerSystemValidation.objects.filter(
                tenant=self.tenant
            ).order_by("system_name")
            self.fields["requestor"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["system_owner"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["qa_lead"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["system", "requestor", "system_owner", "qa_lead", "org_unit"],
        )
        return cleaned_data
