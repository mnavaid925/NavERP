"""Forms for AssetSpaceChargeback (11.17 Tenant & Occupancy Coordination)."""

from decimal import Decimal

from django import forms

from apps.accounting.models import Currency, FiscalPeriod, FixedAsset, GLAccount, Invoice
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.SpaceFacilityAsset._helpers import scope_tenant_querysets
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.SpaceFacilityAsset.AssetBuildingSystems import AssetBuildingSystem
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.models.SpaceFacilityAsset.AssetSpaceChargebacks import AssetSpaceChargeback
from apps.core.models import OrgUnit, Party


class AssetSpaceChargebackForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit form for departmental space chargebacks, CAM/utilities, and TI coordination."""

    # NOTE: currency is GLOBAL (not tenant-owned) and intentionally excluded from _TENANT_FK_MAP.
    _TENANT_FK_MAP = {
        "facility_space": AssetFacilitySpace,
        "shared_building_system": AssetBuildingSystem,
        "lease_contract": AssetLeaseContract,
        "fixed_asset": FixedAsset,
        "charged_org_unit": OrgUnit,
        "occupant_party": Party,
        "fiscal_period": FiscalPeriod,
        "expense_gl_account": GLAccount,
        "recovery_gl_account": GLAccount,
        "ar_invoice": Invoice,
    }

    class Meta:
        model = AssetSpaceChargeback
        fields = [
            "title",
            "coordination_type",
            "allocation_basis",
            "facility_space",
            "shared_building_system",
            "lease_contract",
            "fixed_asset",
            "charged_org_unit",
            "occupant_party",
            "currency",
            "fiscal_period",
            "expense_gl_account",
            "recovery_gl_account",
            "ar_invoice",
            "period_start",
            "period_end",
            "amortization_end_date",
            "allocated_area_sqft",
            "allocation_share_pct",
            "base_cost_amount",
            "shared_cam_amount",
            "utility_recovery_amount",
            "ti_improvement_cost",
            "ti_allowance_offset",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Engineering Floor Allocation & CAM"}),
            "coordination_type": forms.Select(attrs={"class": "form-select"}),
            "allocation_basis": forms.Select(attrs={"class": "form-select"}),
            "facility_space": forms.Select(attrs={"class": "form-select"}),
            "shared_building_system": forms.Select(attrs={"class": "form-select"}),
            "lease_contract": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "charged_org_unit": forms.Select(attrs={"class": "form-select"}),
            "occupant_party": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "fiscal_period": forms.Select(attrs={"class": "form-select"}),
            "expense_gl_account": forms.Select(attrs={"class": "form-select"}),
            "recovery_gl_account": forms.Select(attrs={"class": "form-select"}),
            "ar_invoice": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "amortization_end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "allocated_area_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "allocation_share_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "base_cost_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "shared_cam_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "utility_recovery_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "ti_improvement_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "ti_allowance_offset": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FK_MAP)
        if "currency" in self.fields:
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FK_MAP.keys()))

        period_start = cleaned.get("period_start")
        period_end = cleaned.get("period_end")
        if period_start and period_end and period_end < period_start:
            self.add_error("period_end", "Period end date cannot precede period start date.")

        amort_end = cleaned.get("amortization_end_date")
        if period_start and amort_end and amort_end < period_start:
            self.add_error("amortization_end_date", "Amortization end date cannot precede period start date.")

        expense_gl = cleaned.get("expense_gl_account")
        recovery_gl = cleaned.get("recovery_gl_account")
        if expense_gl is not None and recovery_gl is not None and expense_gl.pk == recovery_gl.pk:
            self.add_error("recovery_gl_account", "Recovery GL account must differ from expense GL account.")

        share_pct = cleaned.get("allocation_share_pct")
        if share_pct is not None and (share_pct < Decimal("0.00") or share_pct > Decimal("100.00")):
            self.add_error("allocation_share_pct", "Allocation share % must be between 0 and 100.")

        for fld, label in (
            ("allocated_area_sqft", "Allocated area"),
            ("base_cost_amount", "Base cost amount"),
            ("shared_cam_amount", "Shared CAM amount"),
            ("utility_recovery_amount", "Utility recovery amount"),
            ("ti_improvement_cost", "TI improvement cost"),
            ("ti_allowance_offset", "TI allowance offset"),
        ):
            val = cleaned.get(fld)
            if val is not None and val < Decimal("0.00"):
                self.add_error(fld, f"{label} cannot be negative.")

        return cleaned
