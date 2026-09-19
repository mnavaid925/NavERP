"""Projects 7.15 Financial & Billing Management — ProjectPaymentRecord forms.
"""
from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.FinancialBillingManagement.PaymentRecords import ProjectPaymentRecord


class ProjectPaymentRecordForm(TenantModelForm):
    class Meta:
        model = ProjectPaymentRecord
        fields = [
            "project",
            "client",
            "billing_run",
            "accounting_invoice",
            "dunning_level",
            "next_follow_up_date",
            "promised_payment_date",
            "promised_amount",
            "dispute_reason",
            "assigned_collector",
            "notes",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "billing_run": forms.Select(attrs={"class": "form-select"}),
            "accounting_invoice": forms.Select(attrs={"class": "form-select"}),
            "dunning_level": forms.Select(attrs={"class": "form-select"}),
            "next_follow_up_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "promised_payment_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "promised_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "dispute_reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "assigned_collector": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "client", "billing_run", "accounting_invoice", "assigned_collector"])
        return cleaned


class PaymentPromiseForm(forms.Form):
    promised_payment_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    promised_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Promise-to-pay terms, contact method, or memo..."}),
    )


class ContactLogForm(forms.Form):
    contact_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    notes = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Customer response, call details, email thread summary..."}),
    )
    next_follow_up_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
