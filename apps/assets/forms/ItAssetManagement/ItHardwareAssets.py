"""Form for IT Hardware Asset Lifecycle & Sanitization records (11.18)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.ItAssetManagement._helpers import scope_tenant_querysets
from apps.assets.models.AssetAnalytics.AssetReplacementPlans import AssetReplacementPlan
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetScrapSalvages import AssetScrapSalvage
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.assets.models.ItAssetManagement.ItHardwareAssets import ItHardwareAsset
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.InventoryManagement.Locations import Location

User = get_user_model()


class ItHardwareAssetForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for IT Hardware Assets [ITHW]."""

    _TENANT_FIELDS = {
        "operational_asset": Asset,
        "fixed_asset": FixedAsset,
        "asset_model": AssetModel,
        "asset_category": AssetCategory,
        "warranty": AssetWarranty,
        "requisition": AssetRequisition,
        "replacement_plan": AssetReplacementPlan,
        "disposal_request": AssetDisposalRequest,
        "scrap_salvage": AssetScrapSalvage,
        "org_unit": OrgUnit,
        "location": Location,
        "custodian_party": Party,
        "vendor_party": Party,
        "employee_profile": EmployeeProfile,
        "owner": User,
    }
    _SANITIZATION_ADMIN_FIELDS = (
        "sanitization_required",
        "sanitization_method",
        "sanitization_status",
        "sanitization_date",
        "sanitization_certificate_ref",
    )

    class Meta:
        model = ItHardwareAsset
        fields = [
            "hostname",
            "fqdn",
            "device_class",
            "serial_number",
            "asset_tag_code",
            "manufacturer",
            "model_name",
            "mac_address",
            "ip_address",
            "operating_system",
            "os_version",
            "cpu_spec",
            "ram_gb",
            "storage_gb",
            "bios_firmware_version",
            "rack_unit_ref",
            "environment",
            "criticality",
            "mdm_enrolled",
            "mdm_platform",
            "mdm_device_id",
            "disk_encryption_status",
            "commissioned_date",
            "assigned_date",
            "vendor_eos_date",
            "vendor_eol_date",
            "refresh_cycle_months",
            "refresh_due_date",
            "estimated_refresh_cost",
            "currency",
            "sanitization_required",
            "sanitization_method",
            "sanitization_status",
            "sanitization_date",
            "sanitization_certificate_ref",
            "operational_asset",
            "fixed_asset",
            "asset_model",
            "asset_category",
            "warranty",
            "requisition",
            "replacement_plan",
            "disposal_request",
            "scrap_salvage",
            "org_unit",
            "location",
            "custodian_party",
            "vendor_party",
            "employee_profile",
            "owner",
            "notes",
        ]
        widgets = {
            "hostname": forms.TextInput(attrs={"placeholder": "e.g. lon-prod-db01"}),
            "fqdn": forms.TextInput(attrs={"placeholder": "e.g. lon-prod-db01.corp.local"}),
            "serial_number": forms.TextInput(attrs={"placeholder": "e.g. SN-9X420-DL380"}),
            "asset_tag_code": forms.TextInput(attrs={"placeholder": "e.g. IT-LAP-0142"}),
            "manufacturer": forms.TextInput(attrs={"placeholder": "e.g. Dell, Apple, Cisco, HPE"}),
            "model_name": forms.TextInput(attrs={"placeholder": "e.g. Latitude 7450 / PowerEdge R760"}),
            "mac_address": forms.TextInput(attrs={"placeholder": "00:1A:2B:3C:4D:5E"}),
            "ip_address": forms.TextInput(attrs={"placeholder": "10.20.4.15"}),
            "operating_system": forms.TextInput(attrs={"placeholder": "e.g. Ubuntu 24.04 LTS, macOS 15"}),
            "os_version": forms.TextInput(attrs={"placeholder": "e.g. 24.04.2 / 15.3"}),
            "cpu_spec": forms.TextInput(attrs={"placeholder": "e.g. Apple M3 Pro / 2x Xeon 6430"}),
            "ram_gb": forms.NumberInput(attrs={"min": "0"}),
            "storage_gb": forms.NumberInput(attrs={"min": "0"}),
            "bios_firmware_version": forms.TextInput(attrs={"placeholder": "e.g. 2.18.0"}),
            "rack_unit_ref": forms.TextInput(attrs={"placeholder": "e.g. DC1-RowA-Rack04-U12"}),
            "mdm_platform": forms.TextInput(attrs={"placeholder": "e.g. Microsoft Intune, Jamf Pro"}),
            "mdm_device_id": forms.TextInput(attrs={"placeholder": "MDM enrollment UUID"}),
            "commissioned_date": forms.DateInput(attrs={"type": "date"}),
            "assigned_date": forms.DateInput(attrs={"type": "date"}),
            "vendor_eos_date": forms.DateInput(attrs={"type": "date"}),
            "vendor_eol_date": forms.DateInput(attrs={"type": "date"}),
            "refresh_cycle_months": forms.NumberInput(attrs={"min": "1", "max": "240"}),
            "refresh_due_date": forms.DateInput(attrs={"type": "date"}),
            "estimated_refresh_cost": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "sanitization_date": forms.DateInput(attrs={"type": "date"}),
            "sanitization_certificate_ref": forms.TextInput(attrs={"placeholder": "e.g. CERT-NIST-2026-088"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Lifecycle notes, BIOS/hardware history, or refresh justification..."}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)
        if "currency" in self.fields:
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")
        is_admin = bool(
            getattr(self.user, "is_superuser", False)
            or getattr(self.user, "is_tenant_admin", False)
        )
        if not is_admin:
            for field_name in self._SANITIZATION_ADMIN_FIELDS:
                self.fields.pop(field_name, None)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, tuple(self._TENANT_FIELDS.keys()))
        refresh_cycle = cleaned.get("refresh_cycle_months")
        if refresh_cycle is not None and refresh_cycle < 1:
            self.add_error("refresh_cycle_months", "Refresh cycle must be at least 1 month.")
        refresh_cost = cleaned.get("estimated_refresh_cost")
        if refresh_cost is not None and refresh_cost < 0:
            self.add_error("estimated_refresh_cost", "Estimated refresh cost cannot be negative.")
        eos = cleaned.get("vendor_eos_date")
        eol = cleaned.get("vendor_eol_date")
        if eos and eol and eol < eos:
            self.add_error("vendor_eol_date", "Vendor EOL date cannot precede End-of-Sale (EOS) date.")
        return cleaned
