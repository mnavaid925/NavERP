"""Sales 8.11 — Forms for `CustomerRenewal`."""
from django import forms

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.CustomerSuccess.CustomerRenewals import CustomerRenewal
from apps.scm.models import SalesOrder


class CustomerRenewalForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerRenewal
        fields = [
            "account",
            "owner",
            "original_order",
            "renewal_name",
            "contract_reference",
            "current_arr",
            "projected_renewal_arr",
            "expansion_amount",
            "currency",
            "renewal_date",
            "target_close_date",
            "stage",
            "churn_risk_flag",
            "renewal_probability_pct",
            "auto_renewal",
            "notice_period_days",
            "expansion_opportunity",
            "notes",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "original_order": forms.Select(attrs={"class": "form-select"}),
            "renewal_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Corp Enterprise Platform 2026-2027 Renewal"}),
            "contract_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. MSA-2024-0089"}),
            "current_arr": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "projected_renewal_arr": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "expansion_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "renewal_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "target_close_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "stage": forms.Select(attrs={"class": "form-select"}),
            "churn_risk_flag": forms.Select(attrs={"class": "form-select"}),
            "renewal_probability_pct": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "auto_renewal": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notice_period_days": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "expansion_opportunity": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            self.fields["owner"].queryset = (
                User.objects.filter(tenant=self.tenant)
                .order_by("username")
            )
            self.fields["original_order"].queryset = (
                SalesOrder.objects.filter(tenant=self.tenant)
                .select_related("customer")
                .order_by("-order_date")
            )
            self.fields["expansion_opportunity"].queryset = (
                Opportunity.objects.filter(tenant=self.tenant)
                .order_by("-created_at")
            )

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["account", "owner", "original_order", "expansion_opportunity"])
        return cleaned_data
