"""Sales 8.15 — UsageMeterRecord forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import _reject_foreign
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.ContractSubscriptionManagement.UsageMeterRecords import (
    USAGE_STATUS_CHOICES,
    UsageMeterRecord,
)


class UsageMeterRecordForm(TenantModelForm):
    class Meta:
        model = UsageMeterRecord
        fields = [
            "subscription",
            "meter_name",
            "unit_of_measure",
            "billing_period_start",
            "billing_period_end",
            "included_allowance",
            "reported_usage",
            "overage_unit_price",
            "status",
            "notes",
        ]
        widgets = {
            "billing_period_start": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "billing_period_end": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "subscription": forms.Select(attrs={"class": "form-select"}),
            "meter_name": forms.TextInput(attrs={"class": "form-input"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input"}),
            "included_allowance": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "reported_usage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "overage_unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["subscription"].queryset = CustomerSubscription.objects.filter(tenant=self.tenant).select_related("account")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["subscription"])
        return cleaned


class UsageMeterRecordFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Search metric name or number...", "class": "form-input"}))
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + USAGE_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    subscription = forms.ModelChoiceField(
        queryset=CustomerSubscription.objects.none(),
        required=False,
        empty_label="All Subscriptions",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["subscription"].queryset = CustomerSubscription.objects.filter(tenant=tenant).select_related("account")
