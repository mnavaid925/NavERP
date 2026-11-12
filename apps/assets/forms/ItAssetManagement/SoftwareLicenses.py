"""Form for Software License Entitlements & SAM Compliance (11.18)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.accounting.models.GeneralLedger.GLAccounts import GLAccount
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.ItAssetManagement._helpers import (
    scope_tenant_querysets,
    validate_masked_key_ref,
)
from apps.assets.models.AssetMaintenance.AssetServiceContracts import AssetServiceContract
from apps.assets.models.ItAssetManagement.SoftwareLicenses import SoftwareLicense
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.scm.models.ProcurementManagement.PurchaseOrders import PurchaseOrder

User = get_user_model()


class SoftwareLicenseForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Software Licenses [ITSW]."""

    _TENANT_FIELDS = {
        "publisher_party": Party,
        "reseller_party": Party,
        "org_unit": OrgUnit,
        "gl_expense_account": GLAccount,
        "purchase_order": PurchaseOrder,
        "service_contract": AssetServiceContract,
        "license_owner": User,
    }

    class Meta:
        model = SoftwareLicense
        fields = [
            "software_name",
            "publisher_name",
            "product_sku",
            "version_edition",
            "software_category",
            "license_type",
            "license_metric",
            "agreement_number",
            "license_key_ref",
            "entitled_quantity",
            "allocated_quantity",
            "active_used_quantity",
            "reclaimable_inactive_count",
            "unit_license_cost",
            "total_annual_spend",
            "currency",
            "effective_date",
            "renewal_date",
            "vendor_eol_date",
            "auto_renew",
            "publisher_party",
            "reseller_party",
            "org_unit",
            "gl_expense_account",
            "purchase_order",
            "service_contract",
            "license_owner",
            "notes",
        ]
        widgets = {
            "software_name": forms.TextInput(attrs={"placeholder": "e.g. Microsoft 365 E5 / JetBrains All Products"}),
            "publisher_name": forms.TextInput(attrs={"placeholder": "e.g. Microsoft, Oracle, Atlassian, Adobe"}),
            "product_sku": forms.TextInput(attrs={"placeholder": "e.g. M365-E5-UNATT"}),
            "version_edition": forms.TextInput(attrs={"placeholder": "e.g. Enterprise 2026"}),
            "agreement_number": forms.TextInput(attrs={"placeholder": "e.g. EA-2026-9941"}),
            "license_key_ref": forms.TextInput(attrs={"placeholder": "Masked ref only, e.g. MS365-****-9X2K"}),
            "entitled_quantity": forms.NumberInput(attrs={"min": "1"}),
            "allocated_quantity": forms.NumberInput(attrs={"min": "0"}),
            "active_used_quantity": forms.NumberInput(attrs={"min": "0"}),
            "reclaimable_inactive_count": forms.NumberInput(attrs={"min": "0"}),
            "unit_license_cost": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "total_annual_spend": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "renewal_date": forms.DateInput(attrs={"type": "date"}),
            "vendor_eol_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "True-up terms, audit scope, or license harvesting notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)
        if "currency" in self.fields:
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")

    def clean_license_key_ref(self):
        return validate_masked_key_ref(self.cleaned_data.get("license_key_ref", ""))

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, tuple(self._TENANT_FIELDS.keys()))
        entitled = cleaned.get("entitled_quantity")
        allocated = cleaned.get("allocated_quantity")
        reclaimable = cleaned.get("reclaimable_inactive_count")
        if entitled is not None and entitled < 1:
            self.add_error("entitled_quantity", "Entitled quantity must be at least 1.")
        if reclaimable is not None and allocated is not None and reclaimable > allocated:
            self.add_error(
                "reclaimable_inactive_count",
                "Reclaimable inactive count cannot exceed allocated quantity.",
            )
        eff = cleaned.get("effective_date")
        ren = cleaned.get("renewal_date")
        if eff and ren and ren < eff:
            self.add_error("renewal_date", "Renewal date cannot precede effective date.")
        return cleaned
