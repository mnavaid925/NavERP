from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessment
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder


class TransactionRiskAssessmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = TransactionRiskAssessment
        exclude = ["tenant", "number", "created_at", "updated_at", "reviewed_at"]
        widgets = {
            "order": forms.Select(attrs={"class": "form-select"}),
            "customer_party": forms.Select(attrs={"class": "form-select"}),
            "user": forms.Select(attrs={"class": "form-select"}),
            "transaction_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "150.00"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "risk_score": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0-100"}),
            "risk_tier": forms.Select(attrs={"class": "form-select"}),
            "recommended_action": forms.Select(attrs={"class": "form-select"}),
            "actual_decision": forms.Select(attrs={"class": "form-select"}),
            "avs_result_code": forms.Select(attrs={"class": "form-select"}),
            "cvv_result_code": forms.Select(attrs={"class": "form-select"}),
            "ip_address": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "198.51.100.42"}),
            "billing_country": forms.TextInput(attrs={"class": "form-input uppercase", "maxlength": "2", "placeholder": "US"}),
            "ip_country": forms.TextInput(attrs={"class": "form-input uppercase", "maxlength": "2", "placeholder": "US"}),
            "is_geo_mismatch": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_proxy_or_vpn": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "device_fingerprint": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "fp_a1b2c3d4..."}),
            "velocity_count_24h": forms.NumberInput(attrs={"class": "form-input", "placeholder": "1"}),
            "risk_factors_summary": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "Triggered rules, velocity spike notes..."}),
            "analyst_user": forms.Select(attrs={"class": "form-select"}),
            "analyst_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Analyst investigation findings and justifications..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant)
            self.fields["customer_party"].queryset = Party.objects.filter(tenant=self.tenant)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        if "user" in self.fields:
            self.fields["user"].queryset = self.fields["user"].queryset.filter(is_active=True)
        if "analyst_user" in self.fields:
            self.fields["analyst_user"].queryset = self.fields["analyst_user"].queryset.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["order", "customer_party"])
        return cleaned

    def clean_risk_score(self):
        score = self.cleaned_data.get("risk_score")
        if score is not None and (score < 0 or score > 100):
            raise forms.ValidationError("Risk score must be an integer between 0 and 100.")
        return score

    def clean_transaction_amount(self):
        val = self.cleaned_data.get("transaction_amount")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Transaction amount cannot be negative.")
        return val
