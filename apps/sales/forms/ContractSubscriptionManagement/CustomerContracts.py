"""Sales 8.15 — CustomerContract forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Document, Party
from apps.crm.models import DocTemplate
from apps.sales.forms._common import _reject_foreign, tenant_users
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import (
    CONTRACT_STATUS_CHOICES,
    CONTRACT_TYPE_CHOICES,
    CustomerContract,
)
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.scm.models.OrderManagement.SalesOrders import SalesOrder


class CustomerContractForm(TenantModelForm):
    class Meta:
        model = CustomerContract
        fields = [
            "account",
            "title",
            "contract_type",
            "status",
            "owner",
            "currency",
            "total_contract_value",
            "annual_contract_value",
            "start_date",
            "end_date",
            "auto_renew",
            "renewal_term_months",
            "notice_period_days",
            "price_uplift_pct",
            "governing_law",
            "originating_quote",
            "originating_order",
            "template",
            "document",
            "special_terms",
            "redline_notes",
            "signoff_contact",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "contract_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "governing_law": forms.TextInput(attrs={"class": "form-input"}),
            "signoff_contact": forms.TextInput(attrs={"class": "form-input"}),
            "total_contract_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "annual_contract_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "price_uplift_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "renewal_term_months": forms.NumberInput(attrs={"class": "form-input"}),
            "notice_period_days": forms.NumberInput(attrs={"class": "form-input"}),
            "special_terms": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "redline_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["account"].queryset = Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()
            self.fields["owner"].queryset = tenant_users(self.tenant)
            self.fields["originating_quote"].queryset = CPQQuote.objects.filter(tenant=self.tenant)
            self.fields["originating_order"].queryset = SalesOrder.objects.filter(tenant=self.tenant)
            self.fields["template"].queryset = DocTemplate.objects.filter(tenant=self.tenant)
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(
            self,
            cleaned,
            ["account", "owner", "originating_quote", "originating_order", "template", "document"],
        )
        return cleaned


class CustomerContractFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Search contracts...", "class": "form-input"}))
    contract_type = forms.ChoiceField(
        choices=[("", "All Types")] + CONTRACT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + CONTRACT_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    owner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Owners",
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
            self.fields["owner"].queryset = tenant_users(tenant)
            self.fields["account"].queryset = Party.objects.filter(tenant=tenant, roles__role="customer").distinct()
