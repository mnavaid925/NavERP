from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure

User = get_user_model()


class RiskControlMeasureForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RiskControlMeasure
        fields = [
            "risk_assessment",
            "control_hierarchy",
            "title",
            "description",
            "assigned_to",
            "due_date",
            "status",
            "design_input",
            "controlled_document",
            "design_verification",
            "implementation_verified",
            "effectiveness_verified",
            "verification_notes",
            "introduces_new_hazard",
            "new_hazard_details",
        ]
        widgets = {
            "risk_assessment": forms.Select(attrs={"class": "form-select"}),
            "control_hierarchy": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Dual Galvanic Isolation Transformers"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe design, protective, or informational mitigation..."}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "design_input": forms.Select(attrs={"class": "form-select"}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "design_verification": forms.Select(attrs={"class": "form-select"}),
            "implementation_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "effectiveness_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "verification_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Objective evidence summary proving implementation and effectiveness..."}),
            "introduces_new_hazard": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "new_hazard_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "If control introduces a secondary hazard, describe here and log a new risk item..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["risk_assessment"].queryset = RiskAssessment.objects.filter(tenant=self.tenant)
            self.fields["assigned_to"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["design_input"].queryset = DesignInput.objects.filter(tenant=self.tenant)
            self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)
            self.fields["design_verification"].queryset = DesignVerification.objects.filter(tenant=self.tenant)
        else:
            self.fields["risk_assessment"].queryset = RiskAssessment.objects.none()
            self.fields["assigned_to"].queryset = User.objects.none()
            self.fields["design_input"].queryset = DesignInput.objects.none()
            self.fields["controlled_document"].queryset = ControlledDocument.objects.none()
            self.fields["design_verification"].queryset = DesignVerification.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["risk_assessment", "assigned_to", "design_input", "controlled_document", "design_verification"],
        )
        return cleaned
