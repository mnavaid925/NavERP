"""Sales 8.15 — ContractObligation forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import _reject_foreign, tenant_users
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.ContractSubscriptionManagement.ContractObligations import (
    OBLIGATION_STATUS_CHOICES,
    OBLIGATION_TYPE_CHOICES,
    PENALTY_STATUS_CHOICES,
    ContractObligation,
)


class ContractObligationForm(TenantModelForm):
    class Meta:
        model = ContractObligation
        fields = [
            "contract",
            "subscription",
            "title",
            "obligation_type",
            "target_metric",
            "due_date",
            "status",
            "penalty_terms",
            "penalty_amount",
            "penalty_status",
            "assigned_to",
            "fulfillment_evidence",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "contract": forms.Select(attrs={"class": "form-select"}),
            "subscription": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "obligation_type": forms.Select(attrs={"class": "form-select"}),
            "target_metric": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "penalty_status": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "penalty_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "penalty_terms": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "fulfillment_evidence": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["contract"].queryset = CustomerContract.objects.filter(tenant=self.tenant)
            self.fields["subscription"].queryset = CustomerSubscription.objects.filter(tenant=self.tenant)
            self.fields["assigned_to"].queryset = tenant_users(self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["contract", "subscription", "assigned_to"])
        return cleaned


class ContractObligationFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Search obligation title or number...", "class": "form-input"}))
    obligation_type = forms.ChoiceField(
        choices=[("", "All Types")] + OBLIGATION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + OBLIGATION_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    contract = forms.ModelChoiceField(
        queryset=CustomerContract.objects.none(),
        required=False,
        empty_label="All Contracts",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Assignees",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["contract"].queryset = CustomerContract.objects.filter(tenant=tenant)
            self.fields["assigned_to"].queryset = tenant_users(tenant)


class ObligationFulfillForm(forms.Form):
    fulfillment_evidence = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Enter proof of SLA compliance, delivery milestone sign-off, or audit link..."}),
    )


class ObligationBreachForm(forms.Form):
    penalty_amount = forms.DecimalField(
        min_value=0,
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
    )
    penalty_status = forms.ChoiceField(
        choices=[("assessed", "Penalty Assessed"), ("credited", "Service Credit Issued")],
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Breach incident details and penalty calculation rationale..."}),
    )
