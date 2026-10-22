"""Sales 8.15 — CustomerSubscription forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.sales.forms._common import _reject_foreign, tenant_users
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import (
    BILLING_CADENCE_CHOICES,
    PRICING_MODEL_CHOICES,
    SUBSCRIPTION_STATUS_CHOICES,
    CustomerSubscription,
)


class CustomerSubscriptionForm(TenantModelForm):
    class Meta:
        model = CustomerSubscription
        fields = [
            "contract",
            "account",
            "subscription_name",
            "plan_code",
            "status",
            "pricing_model",
            "billing_cadence",
            "currency",
            "quantity",
            "unit_price",
            "start_date",
            "current_term_start",
            "current_term_end",
            "trial_ends_at",
            "auto_renew",
            "renewal_notice_days",
            "owner",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "current_term_start": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "current_term_end": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "trial_ends_at": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "subscription_name": forms.TextInput(attrs={"class": "form-input"}),
            "plan_code": forms.TextInput(attrs={"class": "form-input"}),
            "contract": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "pricing_model": forms.Select(attrs={"class": "form-select"}),
            "billing_cadence": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "renewal_notice_days": forms.NumberInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["contract"].queryset = CustomerContract.objects.filter(tenant=self.tenant)
            self.fields["account"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["owner"].queryset = tenant_users(self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["contract", "account", "owner"])
        return cleaned


class CustomerSubscriptionFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Search subscription or plan...", "class": "form-input"}))
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + SUBSCRIPTION_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    pricing_model = forms.ChoiceField(
        choices=[("", "All Pricing Models")] + PRICING_MODEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    billing_cadence = forms.ChoiceField(
        choices=[("", "All Cadences")] + BILLING_CADENCE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    account = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        required=False,
        empty_label="All Accounts",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["account"].queryset = Party.objects.filter(tenant=tenant)


class SubscriptionPauseForm(forms.Form):
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Reason or notes for temporary pause..."}),
    )


class SubscriptionCancelForm(forms.Form):
    cancellation_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Required exit reason or churn feedback..."}),
    )


class SubscriptionUpgradeForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-input"}),
    )
    unit_price = forms.DecimalField(
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
    )
