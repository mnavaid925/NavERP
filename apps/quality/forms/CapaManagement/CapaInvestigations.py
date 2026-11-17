from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment

User = get_user_model()


class CapaInvestigationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CapaInvestigation
        fields = [
            "title",
            "issue_summary",
            "action_type",
            "source_type",
            "source_reference",
            "risk_priority",
            "containment_actions",
            "containment_implemented",
            "containment_verified_by",
            "containment_date",
            "affected_item_code",
            "affected_item_name",
            "affected_lot_numbers",
            "lead_investigator",
            "quality_owner",
            "department",
            "design_project",
            "risk_assessment",
            "status",
            "target_investigation_date",
            "target_closure_date",
            "is_escalated",
            "escalation_reason",
            "closure_summary",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Infusion Pump Occlusion Pressure Sensor Calibration Drift"}),
            "issue_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe defect details, failure mode, immediate observations, and detection context..."}),
            "action_type": forms.Select(attrs={"class": "form-select"}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "source_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. NCR-2026-0042, CMP-0108, AUD-2026-Q1"}),
            "risk_priority": forms.Select(attrs={"class": "form-select"}),
            "containment_actions": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Immediate quarantine holds, line stoppages, stock segregations..."}),
            "containment_implemented": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "containment_verified_by": forms.Select(attrs={"class": "form-select"}),
            "containment_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "affected_item_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PRD-MED-3000"}),
            "affected_item_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Smart Infusion Pump Model 3000"}),
            "affected_lot_numbers": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-A1, LOT-2026-A2"}),
            "lead_investigator": forms.Select(attrs={"class": "form-select"}),
            "quality_owner": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "design_project": forms.Select(attrs={"class": "form-select"}),
            "risk_assessment": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "target_investigation_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "target_closure_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "is_escalated": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "escalation_reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Escalation rationale for executive quality review..."}),
            "closure_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Summary of remediation verification and closure rationale..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["design_project"].queryset = DesignProject.objects.filter(tenant=self.tenant)
            self.fields["risk_assessment"].queryset = RiskAssessment.objects.filter(tenant=self.tenant)
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["lead_investigator"].queryset = user_qs
            self.fields["quality_owner"].queryset = user_qs
            self.fields["containment_verified_by"].queryset = user_qs
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["design_project"].queryset = DesignProject.objects.none()
            self.fields["risk_assessment"].queryset = RiskAssessment.objects.none()
            self.fields["lead_investigator"].queryset = User.objects.none()
            self.fields["quality_owner"].queryset = User.objects.none()
            self.fields["containment_verified_by"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "department",
                "design_project",
                "risk_assessment",
                "lead_investigator",
                "quality_owner",
                "containment_verified_by",
            ],
        )
        return cleaned
