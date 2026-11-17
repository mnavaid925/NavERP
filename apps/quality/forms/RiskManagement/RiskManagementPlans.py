from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan

User = get_user_model()


class RiskManagementPlanForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RiskManagementPlan
        fields = [
            "title",
            "plan_version",
            "status",
            "design_project",
            "lead_risk_manager",
            "department",
            "device_classification",
            "scope_description",
            "matrix_dimension",
            "risk_acceptability_policy",
            "overall_residual_risk_acceptable",
            "overall_benefit_risk_summary",
            "periodic_review_frequency_months",
            "next_review_due_date",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. InfuseFlow Pro 3000 Risk Management Plan"}),
            "plan_version": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 1.0"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "design_project": forms.Select(attrs={"class": "form-select"}),
            "lead_risk_manager": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "device_classification": forms.Select(attrs={"class": "form-select"}),
            "scope_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe device scope, clinical intended use, patient populations, and lifecycle phases covered..."}),
            "matrix_dimension": forms.Select(attrs={"class": "form-select"}),
            "risk_acceptability_policy": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Define policy for acceptability, ALARP thresholds, and criteria for clinical benefit-risk analysis..."}),
            "overall_residual_risk_acceptable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "overall_benefit_risk_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Executive clinical benefit-risk justification summary..."}),
            "periodic_review_frequency_months": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 60}),
            "next_review_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["design_project"].queryset = DesignProject.objects.filter(tenant=self.tenant)
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["lead_risk_manager"].queryset = user_qs
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["design_project"].queryset = DesignProject.objects.none()
            self.fields["lead_risk_manager"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["department", "design_project", "lead_risk_manager"])
        return cleaned
