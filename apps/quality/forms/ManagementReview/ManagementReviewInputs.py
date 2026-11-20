from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.ManagementReview.ManagementReviewInputs import ManagementReviewInput
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport

User = get_user_model()


class ManagementReviewInputForm(TenantModelForm):
    class Meta:
        model = ManagementReviewInput
        fields = [
            "management_review",
            "agenda_order",
            "title",
            "category",
            "presenter",
            "summary_findings",
            "metrics_data",
            "linked_audit",
            "linked_capa",
            "linked_complaint",
            "linked_ncr",
            "attachments_summary",
            "notes",
        ]
        widgets = {
            "management_review": forms.Select(attrs={"class": "form-select"}),
            "agenda_order": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q1 Customer Complaint Trends & Recurrence Analysis"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "presenter": forms.Select(attrs={"class": "form-select"}),
            "summary_findings": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Synthesis of performance data, trends, and compliance metrics"}),
            "metrics_data": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Key metric figures, rates, or tabular numbers"}),
            "linked_audit": forms.Select(attrs={"class": "form-select"}),
            "linked_capa": forms.Select(attrs={"class": "form-select"}),
            "linked_complaint": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "attachments_summary": forms.TextInput(attrs={"class": "form-input", "placeholder": "Slide deck title, doc reference, or file path"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["management_review"].queryset = ManagementReview.objects.filter(
                tenant=self.tenant
            ).order_by("-scheduled_date", "-created_at")
            self.fields["presenter"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["linked_audit"].queryset = QualityAudit.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_capa"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_complaint"].queryset = CustomerComplaint.objects.filter(
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
            ["management_review", "presenter", "linked_audit", "linked_capa", "linked_complaint", "linked_ncr"],
        )
        return cleaned_data
