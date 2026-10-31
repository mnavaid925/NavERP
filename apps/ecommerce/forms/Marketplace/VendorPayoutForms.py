from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorPayouts import VendorPayout


class VendorPayoutForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = VendorPayout
        exclude = [
            "tenant",
            "number",
            "payout_status",
            "net_payout_amount",
            "processed_at",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "vendor": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "gross_sales_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "commission_deducted": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "fees_deducted": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "refunds_deducted": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "tax_withholding_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "payout_method": forms.Select(attrs={"class": "form-select"}),
            "reference_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "Transfer ref or check #"}),
            "tax_year": forms.NumberInput(attrs={"class": "form-input", "placeholder": "2026"}),
            "is_1099_reported": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["vendor"].queryset = MarketplaceVendor.objects.filter(tenant=self.tenant).order_by("store_name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["vendor"])
        return cleaned_data


class PayoutApprovalForm(forms.Form):
    payout_status = forms.ChoiceField(
        choices=VendorPayout.PAYOUT_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reference_code = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Gateway transfer confirmation code"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Approval remarks or payment receipt..."}),
    )
