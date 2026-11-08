from decimal import Decimal

from django import forms

from apps.accounting.models import FixedAsset, GLAccount
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceipt
from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.scm.models import Asset


class AssetCapitalizationForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetCapitalization
        exclude = [
            "tenant",
            "number",
            "status",
            "created_at",
            "updated_at",
            "total_cost_basis",
            "capitalized_by",
            "capitalized_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Capitalization of CNC Milling Machine #1"}),
            "asset_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Haas VF-4SS Vertical Machining Center"}),
            "acquisition_receipt": forms.Select(attrs={"class": "form-select"}),
            "requisition": forms.Select(attrs={"class": "form-select"}),
            "purchase_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "freight_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "installation_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "customs_duties_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "other_initial_costs": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "is_cip_conversion": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "cip_gl_account": forms.Select(attrs={"class": "form-select"}),
            "asset_gl_account": forms.Select(attrs={"class": "form-select"}),
            "depreciation_method": forms.Select(attrs={"class": "form-select"}),
            "useful_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "salvage_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "in_service_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["acquisition_receipt"].queryset = AssetAcquisitionReceipt.objects.filter(tenant=self.tenant)
            self.fields["requisition"].queryset = AssetRequisition.objects.filter(tenant=self.tenant)
            self.fields["cip_gl_account"].queryset = GLAccount.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["asset_gl_account"].queryset = GLAccount.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=self.tenant)

    def clean_useful_life_months(self):
        life = self.cleaned_data.get("useful_life_months")
        if life is not None and life < 1:
            raise forms.ValidationError("Useful life must be at least 1 month.")
        return life

    def clean(self):
        cleaned_data = super().clean()
        cost_fields = [
            "purchase_cost",
            "freight_cost",
            "installation_cost",
            "customs_duties_cost",
            "other_initial_costs",
            "salvage_value",
        ]
        for field in cost_fields:
            val = cleaned_data.get(field)
            if val is not None and val < Decimal("0.00"):
                self.add_error(field, f"{field.replace('_', ' ').capitalize()} cannot be negative.")

        purchase = cleaned_data.get("purchase_cost") or Decimal("0.00")
        freight = cleaned_data.get("freight_cost") or Decimal("0.00")
        installation = cleaned_data.get("installation_cost") or Decimal("0.00")
        customs = cleaned_data.get("customs_duties_cost") or Decimal("0.00")
        other = cleaned_data.get("other_initial_costs") or Decimal("0.00")
        total_basis = purchase + freight + installation + customs + other
        salvage = cleaned_data.get("salvage_value")
        if salvage is not None and salvage > total_basis:
            self.add_error("salvage_value", "Salvage value cannot exceed total capitalized cost basis.")

        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                [
                    "acquisition_receipt",
                    "requisition",
                    "cip_gl_account",
                    "asset_gl_account",
                    "fixed_asset",
                    "operational_asset",
                ],
            )
        return cleaned_data
