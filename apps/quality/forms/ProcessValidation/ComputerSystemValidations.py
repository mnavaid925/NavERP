from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation
from apps.quality.models.ProcessValidation.ValidationProtocols import ValidationProtocol
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment

User = get_user_model()


class ComputerSystemValidationForm(TenantModelForm):
    class Meta:
        model = ComputerSystemValidation
        fields = [
            "system_name",
            "version_release",
            "vendor_name",
            "gamp_category",
            "gxp_impact",
            "validation_approach",
            "hosting_model",
            "is_part_11_compliant",
            "requires_audit_trail",
            "has_disaster_recovery_plan",
            "traceability_status",
            "urs_requirements_count",
            "test_scripts_count",
            "deviations_found_count",
            "status",
            "validated_date",
            "periodic_review_frequency_months",
            "last_review_date",
            "next_review_due",
            "description",
            "system_owner",
            "quality_lead",
            "validation_protocol",
            "urs_document",
            "vsr_document",
            "risk_assessment",
        ]
        widgets = {
            "system_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. NavERP Quality Management Suite"}),
            "version_release": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. v2.4.0"}),
            "vendor_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Internal Development / SAP / Veeva"}),
            "gamp_category": forms.Select(attrs={"class": "form-select"}),
            "gxp_impact": forms.Select(attrs={"class": "form-select"}),
            "validation_approach": forms.Select(attrs={"class": "form-select"}),
            "hosting_model": forms.Select(attrs={"class": "form-select"}),
            "is_part_11_compliant": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_audit_trail": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "has_disaster_recovery_plan": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "traceability_status": forms.Select(attrs={"class": "form-select"}),
            "urs_requirements_count": forms.NumberInput(attrs={"class": "form-input"}),
            "test_scripts_count": forms.NumberInput(attrs={"class": "form-input"}),
            "deviations_found_count": forms.NumberInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "validated_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "periodic_review_frequency_months": forms.NumberInput(attrs={"class": "form-input"}),
            "last_review_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_review_due": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Intended use, GxP functions, architecture, and network interfaces"}),
            "system_owner": forms.Select(attrs={"class": "form-select"}),
            "quality_lead": forms.Select(attrs={"class": "form-select"}),
            "validation_protocol": forms.Select(attrs={"class": "form-select"}),
            "urs_document": forms.Select(attrs={"class": "form-select"}),
            "vsr_document": forms.Select(attrs={"class": "form-select"}),
            "risk_assessment": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "username")
            self.fields["system_owner"].queryset = user_qs
            self.fields["quality_lead"].queryset = user_qs
            self.fields["validation_protocol"].queryset = ValidationProtocol.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["urs_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["vsr_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["risk_assessment"].queryset = RiskAssessment.objects.filter(tenant=self.tenant).order_by("number")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "system_owner",
                "quality_lead",
                "validation_protocol",
                "urs_document",
                "vsr_document",
                "risk_assessment",
            ],
        )
        return cleaned
