from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.DataIntegrity.DataIntegrityAssessments import DataIntegrityAssessment
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation

User = get_user_model()


class DataIntegrityAssessmentForm(TenantModelForm):
    class Meta:
        model = DataIntegrityAssessment
        fields = [
            "title",
            "assessment_scope",
            "system",
            "org_unit",
            "lead_assessor",
            "qa_reviewer",
            "assessment_date",
            "next_review_due",
            "attributable_rating",
            "legible_rating",
            "contemporaneous_rating",
            "original_rating",
            "accurate_rating",
            "complete_rating",
            "consistent_rating",
            "enduring_rating",
            "available_rating",
            "overall_risk_level",
            "vulnerabilities_summary",
            "remediation_plan",
            "linked_capa",
            "linked_ncr",
            "status",
            "comments",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LIMS Raw Analytical Data Integrity & Audit Trail Assessment"}),
            "assessment_scope": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. QC Chromatography Data System (CDS) & Electronic Signatures"}),
            "system": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "lead_assessor": forms.Select(attrs={"class": "form-select"}),
            "qa_reviewer": forms.Select(attrs={"class": "form-select"}),
            "assessment_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_review_due": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "attributable_rating": forms.Select(attrs={"class": "form-select"}),
            "legible_rating": forms.Select(attrs={"class": "form-select"}),
            "contemporaneous_rating": forms.Select(attrs={"class": "form-select"}),
            "original_rating": forms.Select(attrs={"class": "form-select"}),
            "accurate_rating": forms.Select(attrs={"class": "form-select"}),
            "complete_rating": forms.Select(attrs={"class": "form-select"}),
            "consistent_rating": forms.Select(attrs={"class": "form-select"}),
            "enduring_rating": forms.Select(attrs={"class": "form-select"}),
            "available_rating": forms.Select(attrs={"class": "form-select"}),
            "overall_risk_level": forms.Select(attrs={"class": "form-select"}),
            "vulnerabilities_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Identified vulnerabilities across ALCOA+ dimensions..."}),
            "remediation_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Corrective technical and procedural controls to be implemented..."}),
            "linked_capa": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "comments": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["system"].queryset = ComputerSystemValidation.objects.filter(
                tenant=self.tenant
            ).order_by("system_name")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["lead_assessor"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["qa_reviewer"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["linked_capa"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["system", "org_unit", "lead_assessor", "qa_reviewer", "linked_capa", "linked_ncr"],
        )
        return cleaned_data
