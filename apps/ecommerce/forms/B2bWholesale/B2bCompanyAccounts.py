from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount


class B2bCompanyAccountForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = B2bCompanyAccount
        exclude = ["tenant", "number", "created_at", "updated_at", "available_credit"]
        widgets = {
            "company_party": forms.Select(attrs={"class": "form-select"}),
            "primary_contact": forms.Select(attrs={"class": "form-select"}),
            "preferred_currency": forms.Select(attrs={"class": "form-select"}),
            "company_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Industrial Supplies Ltd"}),
            "company_tax_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US-123456789 or GB987654321"}),
            "business_registration_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. REG-8839201"}),
            "website": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://www.acme-industrial.com"}),
            "industry": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Manufacturing, Construction"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "100000.00"}),
            "payment_terms": forms.Select(attrs={"class": "form-select"}),
            "credit_status": forms.Select(attrs={"class": "form-select"}),
            "requires_po_number": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_order_approval": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "approval_threshold_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "5000.00"}),
            "default_approver": forms.Select(attrs={"class": "form-select"}),
            "punchout_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "punchout_protocol": forms.Select(attrs={"class": "form-select"}),
            "punchout_identity": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. DUNS-019283746"}),
            "punchout_shared_secret": forms.PasswordInput(render_value=False, attrs={"class": "form-input font-mono", "placeholder": "Secret token / password"}),
            "punchout_return_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://procurement.buyer.com/punchout/callback"}),
            "wholesale_discount_percent": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "15.00"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Credit underwriting notes, special trade clauses..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if self.tenant:
            self.fields["company_party"].queryset = Party.objects.filter(tenant=self.tenant)
        self.fields["preferred_currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["primary_contact"].queryset = User.objects.filter(is_active=True)
        self.fields["default_approver"].queryset = User.objects.filter(is_active=True)

    def clean_credit_limit(self):
        val = self.cleaned_data.get("credit_limit")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Credit limit cannot be negative.")
        return val

    def clean_wholesale_discount_percent(self):
        val = self.cleaned_data.get("wholesale_discount_percent")
        if val is not None and (val < Decimal("0.00") or val > Decimal("100.00")):
            raise forms.ValidationError("Wholesale discount percentage must be between 0% and 100%.")
        return val

    def clean_approval_threshold_amount(self):
        val = self.cleaned_data.get("approval_threshold_amount")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Approval threshold amount cannot be negative.")
        return val

    def clean_punchout_shared_secret(self):
        val = self.cleaned_data.get("punchout_shared_secret")
        if not val and self.instance and self.instance.pk:
            return self.instance.punchout_shared_secret
        return val or ""

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["company_party"])
        return cleaned
