"""Projects 7.15 Financial & Billing Management — ProjectRateCard forms.
"""
from django import forms

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.FinancialBillingManagement.RateCards import ProjectRateCard


class ProjectRateCardForm(TenantModelForm):
    class Meta:
        model = ProjectRateCard
        fields = [
            "name",
            "project",
            "client",
            "role_name",
            "activity_code",
            "hourly_rate",
            "expense_markup_pct",
            "currency",
            "effective_from",
            "effective_to",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Standard Engineering 2026"}),
            "project": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "role_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Senior Solutions Architect"}),
            "activity_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. direct_project"}),
            "hourly_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "expense_markup_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "effective_from": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_to": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "client"])
        return cleaned
