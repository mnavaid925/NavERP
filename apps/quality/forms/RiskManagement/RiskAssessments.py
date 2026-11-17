from django import forms

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan


class RiskAssessmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RiskAssessment
        fields = [
            "plan",
            "analysis_type",
            "hazard_category",
            "hazard_description",
            "hazardous_situation",
            "foreseeable_sequence_of_events",
            "potential_harm",
            "item_function",
            "failure_mode",
            "failure_cause",
            "failure_effect",
            "initial_severity",
            "initial_probability",
            "initial_detectability",
            "residual_severity",
            "residual_probability",
            "residual_detectability",
            "residual_risk_acceptable",
            "bra_required",
            "benefit_risk_justification",
            "disclosed_in_ifu",
            "design_input",
            "lifecycle_status",
        ]
        widgets = {
            "plan": forms.Select(attrs={"class": "form-select"}),
            "analysis_type": forms.Select(attrs={"class": "form-select"}),
            "hazard_category": forms.Select(attrs={"class": "form-select"}),
            "hazard_description": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Ingress of conductive fluids"}),
            "hazardous_situation": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Describe circumstance exposing patient or user to hazard..."}),
            "foreseeable_sequence_of_events": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Chain of events (e.g. Seal degrades -> saline leaks onto circuit board -> short circuit)..."}),
            "potential_harm": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Harm to patient/user (e.g. Electrical shock, thermal burn, therapy interruption)..."}),
            "item_function": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Power Supply Board / Fluid Delivery Line"}),
            "failure_mode": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Short circuit, seal rupture, false occlusion alarm"}),
            "failure_cause": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Root physical cause or failure mechanism..."}),
            "failure_effect": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Downstream consequence on device or clinical therapy..."}),
            "initial_severity": forms.Select(attrs={"class": "form-select"}),
            "initial_probability": forms.Select(attrs={"class": "form-select"}),
            "initial_detectability": forms.Select(attrs={"class": "form-select"}),
            "residual_severity": forms.Select(attrs={"class": "form-select"}),
            "residual_probability": forms.Select(attrs={"class": "form-select"}),
            "residual_detectability": forms.Select(attrs={"class": "form-select"}),
            "residual_risk_acceptable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "bra_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "benefit_risk_justification": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Required if residual risk is in ALARP zone: justify clinical benefits outweighing risk..."}),
            "disclosed_in_ifu": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "design_input": forms.Select(attrs={"class": "form-select"}),
            "lifecycle_status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["plan"].queryset = RiskManagementPlan.objects.filter(tenant=self.tenant)
            self.fields["design_input"].queryset = DesignInput.objects.filter(tenant=self.tenant)
        else:
            self.fields["plan"].queryset = RiskManagementPlan.objects.none()
            self.fields["design_input"].queryset = DesignInput.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["plan", "design_input"])

        res_s = cleaned.get("residual_severity")
        res_p = cleaned.get("residual_probability")
        acceptable = cleaned.get("residual_risk_acceptable")
        justification = (cleaned.get("benefit_risk_justification") or "").strip()

        if res_s and res_p:
            try:
                level = RiskAssessment.calculate_level(int(res_s), int(res_p))
            except (ValueError, TypeError):
                level = ""

            if level == "unacceptable" and acceptable:
                self.add_error(
                    "residual_risk_acceptable",
                    "Residual risk is in the Unacceptable zone (Severity x Probability >= 15). It cannot be marked acceptable under ISO 14971 without further risk reduction.",
                )
            elif level == "alarp" and acceptable and not justification:
                self.add_error(
                    "benefit_risk_justification",
                    "A Clinical Benefit-Risk Analysis (BRA) justification is mandatory when accepting a residual risk in the ALARP zone.",
                )

        return cleaned
