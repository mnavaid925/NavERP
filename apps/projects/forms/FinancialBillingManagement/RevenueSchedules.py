"""Projects 7.15 Financial & Billing Management — ProjectRevenueSchedule forms.
"""
from django import forms
from django.utils import timezone

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.FinancialBillingManagement.RevenueSchedules import ProjectRevenueSchedule


class ProjectRevenueScheduleForm(TenantModelForm):
    class Meta:
        model = ProjectRevenueSchedule
        fields = [
            "project",
            "milestone",
            "recognition_date",
            "fiscal_period",
            "method",
            "contract_amount",
            "completion_percent",
            "recognized_amount",
            "deferred_amount",
            "unbilled_amount",
            "cost_center",
            "gl_account",
            "notes",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "milestone": forms.Select(attrs={"class": "form-select"}),
            "recognition_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "fiscal_period": forms.Select(attrs={"class": "form-select"}),
            "method": forms.Select(attrs={"class": "form-select"}),
            "contract_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "completion_percent": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "recognized_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "deferred_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "unbilled_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "gl_account": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "milestone", "fiscal_period", "cost_center", "gl_account"])
        project = cleaned.get("project")
        milestone = cleaned.get("milestone")
        if milestone and project and milestone.project_id != project.pk:
            self.add_error("milestone", "The selected milestone does not belong to the chosen project.")
        return cleaned


class RevenueScheduleRecognizeForm(forms.Form):
    recognition_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Recognition rationale or audit note..."}),
    )
