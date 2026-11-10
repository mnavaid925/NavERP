from django import forms

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory, AssetServiceContract
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.core.models import Document, Party
from apps.scm.models import Asset as OperationalAsset


class AssetWarrantyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetWarranty
        fields = [
            "title",
            "warranty_certificate_number",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "warrantor_party",
            "currency",
            "warranty_type",
            "coverage_scope",
            "start_date",
            "end_date",
            "meter_type",
            "meter_limit",
            "parts_coverage_percent",
            "labor_coverage_percent",
            "travel_dispatch_covered",
            "deductible_amount",
            "contract_purchase_price",
            "terms_and_conditions",
            "contract_document",
            "service_contract",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 5-Year CNC Spindle & Drive Extended Warranty"}),
            "warranty_certificate_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. WTY-CAT-2026-98124"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "warrantor_party": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "warranty_type": forms.Select(attrs={"class": "form-select"}),
            "coverage_scope": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "meter_type": forms.Select(attrs={"class": "form-select"}),
            "meter_limit": forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 5000"}),
            "parts_coverage_percent": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "labor_coverage_percent": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "travel_dispatch_covered": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "deductible_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "contract_purchase_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "terms_and_conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Coverage rules, exclusions, preventive maintenance requirements..."}),
            "contract_document": forms.Select(attrs={"class": "form-select"}),
            "service_contract": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["asset_category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["warrantor_party"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="vendor",
            ).distinct()
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
            self.fields["contract_document"].queryset = Document.objects.filter(tenant=self.tenant)
            self.fields["service_contract"].queryset = AssetServiceContract.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "Warranty expiration date cannot precede inception date.")

        reject_foreign(
            self,
            cleaned_data,
            [
                "fixed_asset",
                "operational_asset",
                "asset_category",
                "warrantor_party",
                "contract_document",
                "service_contract",
            ],
        )
        return cleaned_data
