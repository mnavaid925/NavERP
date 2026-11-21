from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.DataIntegrity.AuditTrailReviews import AuditTrailReview
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation

User = get_user_model()


class AuditTrailReviewForm(TenantModelForm):
    class Meta:
        model = AuditTrailReview
        fields = [
            "title",
            "system",
            "review_type",
            "audit_source",
            "period_start",
            "period_end",
            "reviewer",
            "qa_approver",
            "review_date",
            "records_sampled_count",
            "anomalies_detected_count",
            "anomaly_severity",
            "findings_summary",
            "disposition",
            "status",
            "linked_ncr",
            "linked_capa",
            "qa_comments",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Monthly GxP Database Audit Trail Review - Manufacturing Execution"}),
            "system": forms.Select(attrs={"class": "form-select"}),
            "review_type": forms.Select(attrs={"class": "form-select"}),
            "audit_source": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "reviewer": forms.Select(attrs={"class": "form-select"}),
            "qa_approver": forms.Select(attrs={"class": "form-select"}),
            "review_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "records_sampled_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "anomalies_detected_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "anomaly_severity": forms.Select(attrs={"class": "form-select"}),
            "findings_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Audit trail log analysis, sequence verification, deleted entry checks, user access exceptions..."}),
            "disposition": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "linked_ncr": forms.Select(attrs={"class": "form-select"}),
            "linked_capa": forms.Select(attrs={"class": "form-select"}),
            "qa_comments": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["system"].queryset = ComputerSystemValidation.objects.filter(
                tenant=self.tenant
            ).order_by("system_name")
            self.fields["reviewer"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["qa_approver"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["linked_ncr"].queryset = NonConformanceReport.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["linked_capa"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["system", "reviewer", "qa_approver", "linked_ncr", "linked_capa"],
        )
        return cleaned_data
