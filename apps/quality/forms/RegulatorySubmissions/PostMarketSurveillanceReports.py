from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.RegulatorySubmissions.PostMarketSurveillanceReports import PostMarketSurveillanceReport
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration

User = get_user_model()


class PostMarketSurveillanceReportForm(TenantModelForm):
    class Meta:
        model = PostMarketSurveillanceReport
        fields = [
            "report_title",
            "report_type",
            "product_registration",
            "device_model_family",
            "reporting_period_start",
            "reporting_period_end",
            "units_distributed",
            "total_complaints_count",
            "serious_incidents_count",
            "field_actions_count",
            "benefit_risk_conclusion",
            "benefit_risk_rationale",
            "pmcf_action_required",
            "pmcf_action_summary",
            "status",
            "prepared_by",
            "approved_by",
            "approval_date",
            "next_report_due_date",
            "notes",
        ]
        widgets = {
            "report_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EU MDR Annual PSUR — CardioPulse Family (2025-2026)"}),
            "report_type": forms.Select(attrs={"class": "form-select"}),
            "product_registration": forms.Select(attrs={"class": "form-select"}),
            "device_model_family": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CardioPulse CPM Series"}),
            "reporting_period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "reporting_period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "units_distributed": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "total_complaints_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "serious_incidents_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "field_actions_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "benefit_risk_conclusion": forms.Select(attrs={"class": "form-select"}),
            "benefit_risk_rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Summary of benefit-risk analysis, complaint rates, clinical trends, and residual risk acceptability..."}),
            "pmcf_action_required": forms.CheckboxInput(attrs={"class": "form-check"}),
            "pmcf_action_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Post-market clinical follow-up activities planned, registries, survey studies..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "prepared_by": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "approval_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_report_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["product_registration"].queryset = ProductRegistration.objects.filter(
                tenant=self.tenant
            ).order_by("product_name")
            self.fields["prepared_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["approved_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["product_registration", "prepared_by", "approved_by"],
        )
        start_date = cleaned_data.get("reporting_period_start")
        end_date = cleaned_data.get("reporting_period_end")
        if start_date and end_date and end_date < start_date:
            self.add_error("reporting_period_end", "Reporting period end date cannot be prior to start date.")
        return cleaned_data
