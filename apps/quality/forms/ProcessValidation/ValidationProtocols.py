from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.ProcessValidation.ValidationProtocols import ValidationProtocol

User = get_user_model()


class ValidationProtocolForm(TenantModelForm):
    class Meta:
        model = ValidationProtocol
        fields = [
            "title",
            "description",
            "protocol_stage",
            "target_type",
            "status",
            "revalidation_trigger",
            "equipment_tag",
            "process_name",
            "facility_area",
            "item_code",
            "target_completion_date",
            "actual_completion_date",
            "revalidation_due_date",
            "test_runs_planned",
            "test_runs_completed",
            "acceptance_criteria",
            "summary_conclusions",
            "deviations_encountered",
            "critical_parameters_verified",
            "department",
            "lead_author",
            "qa_reviewer",
            "final_approver",
            "governing_document",
            "triggering_change",
            "calibration_gage",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Autoclave 04 IQ/OQ Qualification Protocol"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Scope, objectives, and regulatory background"}),
            "protocol_stage": forms.Select(attrs={"class": "form-select"}),
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "revalidation_trigger": forms.Select(attrs={"class": "form-select"}),
            "equipment_tag": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EQ-AUTOCLAVE-04"}),
            "process_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Terminal Moist Heat Sterilization"}),
            "facility_area": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Cleanroom Suite ISO 7"}),
            "item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FG-10042"}),
            "target_completion_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_completion_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "revalidation_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "test_runs_planned": forms.NumberInput(attrs={"class": "form-input"}),
            "test_runs_completed": forms.NumberInput(attrs={"class": "form-input"}),
            "acceptance_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Pass/fail tolerances and statistical parameters"}),
            "summary_conclusions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Summary conclusions, deviations, and disposition"}),
            "deviations_encountered": forms.NumberInput(attrs={"class": "form-input"}),
            "critical_parameters_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "lead_author": forms.Select(attrs={"class": "form-select"}),
            "qa_reviewer": forms.Select(attrs={"class": "form-select"}),
            "final_approver": forms.Select(attrs={"class": "form-select"}),
            "governing_document": forms.Select(attrs={"class": "form-select"}),
            "triggering_change": forms.Select(attrs={"class": "form-select"}),
            "calibration_gage": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "username")
            self.fields["lead_author"].queryset = user_qs
            self.fields["qa_reviewer"].queryset = user_qs
            self.fields["final_approver"].queryset = user_qs
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["governing_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["triggering_change"].queryset = DocumentChangeOrder.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["calibration_gage"].queryset = CalibrationGage.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "department",
                "lead_author",
                "qa_reviewer",
                "final_approver",
                "governing_document",
                "triggering_change",
                "calibration_gage",
            ],
        )
        return cleaned
