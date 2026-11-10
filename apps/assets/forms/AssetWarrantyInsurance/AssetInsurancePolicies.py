from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetWarrantyInsurance.AssetInsurancePolicies import AssetInsurancePolicy
from apps.core.models import Document, Party
from apps.scm.models import Asset as OperationalAsset

User = get_user_model()


class AssetInsurancePolicyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetInsurancePolicy
        fields = [
            "policy_number",
            "title",
            "policy_type",
            "valuation_basis",
            "underwriter_party",
            "broker_party",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "currency",
            "effective_date",
            "expiration_date",
            "total_insured_value",
            "deductible_retention",
            "coinsurance_percentage",
            "annual_premium",
            "premium_frequency",
            "coverage_terms",
            "policy_document",
            "risk_manager",
        ]
        widgets = {
            "policy_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. POL-PROP-2026-90412"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Plant Machinery Breakdown & Boiler Pressure Vessel Schedule"}),
            "policy_type": forms.Select(attrs={"class": "form-select"}),
            "valuation_basis": forms.Select(attrs={"class": "form-select"}),
            "underwriter_party": forms.Select(attrs={"class": "form-select"}),
            "broker_party": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "effective_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "expiration_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "total_insured_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "deductible_retention": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "coinsurance_percentage": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "annual_premium": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "premium_frequency": forms.Select(attrs={"class": "form-select"}),
            "coverage_terms": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Territorial endorsements, named perils, exclusions, warranty clauses..."}),
            "policy_document": forms.Select(attrs={"class": "form-select"}),
            "risk_manager": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["underwriter_party"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="vendor",
            ).distinct()
            self.fields["broker_party"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="vendor",
            ).distinct()
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["asset_category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
            self.fields["policy_document"].queryset = Document.objects.filter(tenant=self.tenant)
            self.fields["risk_manager"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        eff = cleaned_data.get("effective_date")
        exp = cleaned_data.get("expiration_date")
        if eff and exp and exp < eff:
            self.add_error("expiration_date", "Policy expiration date cannot precede effective inception date.")

        reject_foreign(
            self,
            cleaned_data,
            [
                "underwriter_party",
                "broker_party",
                "fixed_asset",
                "operational_asset",
                "asset_category",
                "policy_document",
                "risk_manager",
            ],
        )
        return cleaned_data
