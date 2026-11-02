from decimal import Decimal
from django import forms

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.FraudRisk.ChargebackDisputes import ChargebackDispute
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder


class ChargebackDisputeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ChargebackDispute
        exclude = ["tenant", "number", "created_at", "updated_at", "representment_submitted_at", "resolved_at"]
        widgets = {
            "order": forms.Select(attrs={"class": "form-select"}),
            "customer_party": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "dispute_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "250.00"}),
            "dispute_fee": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "15.00"}),
            "gateway_dispute_id": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "dp_1N9Abc2eZvKYlo2C"}),
            "payment_method_type": forms.Select(attrs={"class": "form-select"}),
            "card_brand": forms.TextInput(attrs={"class": "form-input", "placeholder": "Visa, Mastercard, Amex"}),
            "reason_category": forms.Select(attrs={"class": "form-select"}),
            "reason_code": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. 10.4 or 4837"}),
            "stage": forms.Select(attrs={"class": "form-select"}),
            "evidence_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "evidence_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Delivery confirmation tracking #, signed receipt details, customer communications..."}),
            "representment_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Formal rebuttal letter text submitted to processor..."}),
            "outcome_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Verdict explanation, refund offset notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant)
            self.fields["customer_party"].queryset = Party.objects.filter(tenant=self.tenant)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)

    def clean_dispute_amount(self):
        val = self.cleaned_data.get("dispute_amount")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Dispute amount cannot be negative.")
        return val

    def clean_dispute_fee(self):
        val = self.cleaned_data.get("dispute_fee")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Dispute fee cannot be negative.")
        return val
