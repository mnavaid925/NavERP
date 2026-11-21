from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.DataIntegrity.ElectronicRecordPolicies import ElectronicRecordPolicy
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation

User = get_user_model()


class ElectronicRecordPolicyForm(TenantModelForm):
    class Meta:
        model = ElectronicRecordPolicy
        fields = [
            "title",
            "record_type_name",
            "record_category",
            "target_model_name",
            "system",
            "governing_sop",
            "is_part_11_regulated",
            "is_annex_11_regulated",
            "signature_requirement",
            "reauthentication_required",
            "dual_signature_required",
            "audit_trail_mandatory",
            "retention_period_years",
            "storage_format",
            "backup_frequency",
            "legal_hold",
            "status",
            "system_owner",
            "qa_approver",
            "approval_date",
            "description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Batch Production Record 21 CFR Part 11 Governance Policy"}),
            "record_type_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Electronic Batch Record (eBR)"}),
            "record_category": forms.Select(attrs={"class": "form-select"}),
            "target_model_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. BatchRecord / QFQC"}),
            "system": forms.Select(attrs={"class": "form-select"}),
            "governing_sop": forms.Select(attrs={"class": "form-select"}),
            "is_part_11_regulated": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_annex_11_regulated": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "signature_requirement": forms.Select(attrs={"class": "form-select"}),
            "reauthentication_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "dual_signature_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "audit_trail_mandatory": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "retention_period_years": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 100}),
            "storage_format": forms.Select(attrs={"class": "form-select"}),
            "backup_frequency": forms.Select(attrs={"class": "form-select"}),
            "legal_hold": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "system_owner": forms.Select(attrs={"class": "form-select"}),
            "qa_approver": forms.Select(attrs={"class": "form-select"}),
            "approval_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Governance scope, ALCOA+ controls, and electronic record boundary specifications..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["system"].queryset = ComputerSystemValidation.objects.filter(
                tenant=self.tenant
            ).order_by("system_name")
            self.fields["governing_sop"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant
            ).order_by("title")
            self.fields["system_owner"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["qa_approver"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["system", "governing_sop", "system_owner", "qa_approver"])
        return cleaned_data
