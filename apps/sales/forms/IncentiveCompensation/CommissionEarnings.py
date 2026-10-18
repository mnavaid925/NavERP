"""Sales 8.10 — Forms for `CommissionEarning`."""
from django import forms

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.IncentiveCompensation.CommissionEarnings import CommissionEarning
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan
from apps.scm.models import SalesOrder


class CommissionEarningForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CommissionEarning
        fields = [
            "plan",
            "payee",
            "opportunity",
            "sales_order",
            "credit_type",
            "split_percentage",
            "deal_amount",
            "attainment_pct_at_close",
            "applied_rate_pct",
            "spif_amount",
            "deal_currency",
            "exchange_rate",
            "status",
            "earned_date",
            "clawback_parent",
        ]
        widgets = {
            "plan": forms.Select(attrs={"class": "form-select"}),
            "payee": forms.Select(attrs={"class": "form-select"}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "credit_type": forms.Select(attrs={"class": "form-select"}),
            "split_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "deal_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "attainment_pct_at_close": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "applied_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "spif_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "deal_currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "earned_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "clawback_parent": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["plan"].queryset = CommissionPlan.objects.filter(tenant=self.tenant, status="active")
            self.fields["payee"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["opportunity"].queryset = Opportunity.objects.filter(tenant=self.tenant)
            self.fields["sales_order"].queryset = SalesOrder.objects.filter(tenant=self.tenant)
            self.fields["clawback_parent"].queryset = CommissionEarning.objects.filter(tenant=self.tenant)
        else:
            self.fields["plan"].queryset = CommissionPlan.objects.none()
            self.fields["payee"].queryset = User.objects.none()
            self.fields["opportunity"].queryset = Opportunity.objects.none()
            self.fields["sales_order"].queryset = SalesOrder.objects.none()
            self.fields["clawback_parent"].queryset = CommissionEarning.objects.none()
        self.fields["deal_currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["plan", "payee", "opportunity", "sales_order", "clawback_parent"])
        return cleaned
