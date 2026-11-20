from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigation


class ComplaintInvestigationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ComplaintInvestigation
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "status",
            "qa_approved_by",
            "qa_approved_date",
        ]
        widgets = {
            "target_completion_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "actual_completion_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "dhr_review_summary": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "sample_testing_findings": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "health_hazard_evaluation": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "root_cause_narrative": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
            "investigation_conclusion": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            if "complaint" in self.fields:
                from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
                self.fields["complaint"].queryset = CustomerComplaint.objects.filter(tenant=self.tenant)
            if "lead_investigator" in self.fields:
                self.fields["lead_investigator"].queryset = get_user_model().objects.filter(tenant=self.tenant)
            if "risk_assessment" in self.fields:
                from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
                self.fields["risk_assessment"].queryset = RiskAssessment.objects.filter(tenant=self.tenant)
            if "capa" in self.fields:
                from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
                self.fields["capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            if "ncr" in self.fields:
                from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
                self.fields["ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["complaint", "lead_investigator", "risk_assessment", "capa", "ncr"],
        )

        capa_required = cleaned_data.get("capa_required")
        capa = cleaned_data.get("capa")
        ncr = cleaned_data.get("ncr")
        conclusion = cleaned_data.get("investigation_conclusion")
        if capa_required and not (capa or ncr or (conclusion and conclusion.strip())):
            self.add_error(
                "investigation_conclusion",
                "When CAPA is required, link a CAPA/NCR or document the formal remediation plan in the conclusion.",
            )

        return cleaned_data
