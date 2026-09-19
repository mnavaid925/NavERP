"""Projects 7.15 Financial & Billing Management — ProjectBillingRun forms.
"""
from django import forms

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.FinancialBillingManagement.BillingRuns import ProjectBillingRun


class ProjectBillingRunForm(TenantModelForm):
    class Meta:
        model = ProjectBillingRun
        fields = [
            "project",
            "client",
            "sow",
            "milestone",
            "billing_type",
            "run_date",
            "cutoff_date",
            "labor_amount",
            "expense_amount",
            "fee_amount",
            "tax_code",
            "currency",
            "exchange_rate",
            "delivery_channel",
            "recipient_email",
            "notes",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "sow": forms.Select(attrs={"class": "form-select"}),
            "milestone": forms.Select(attrs={"class": "form-select"}),
            "billing_type": forms.Select(attrs={"class": "form-select"}),
            "run_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "cutoff_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "labor_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "expense_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "fee_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "tax_code": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.00000001"}),
            "delivery_channel": forms.Select(attrs={"class": "form-select"}),
            "recipient_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "client.billing@example.com"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "client", "sow", "milestone", "tax_code"])
        project = cleaned.get("project")
        sow = cleaned.get("sow")
        milestone = cleaned.get("milestone")
        if sow and project and sow.project_id != project.pk:
            self.add_error("sow", "The selected statement of work does not belong to the chosen project.")
        if milestone and project and milestone.project_id != project.pk:
            self.add_error("milestone", "The selected milestone does not belong to the chosen project.")
        return cleaned


class BillingRunDispatchForm(forms.Form):
    recipient_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "client.invoices@company.com"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Optional delivery message or memo..."}),
    )
