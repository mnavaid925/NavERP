"""Forms for AssetBuildingSystem (11.17 HVAC & Building Systems / Infrastructure)."""

from decimal import Decimal

from django import forms

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.SpaceFacilityAsset._helpers import scope_tenant_querysets
from apps.assets.models.AssetCompliance.AssetPermitLicenses import AssetPermitLicense
from apps.assets.models.AssetDocumentKnowledge._validators import (
    is_asset_document_readable,
    readable_asset_document_q,
)
from apps.assets.models.AssetDocumentKnowledge.AssetDocuments import AssetDocument
from apps.assets.models.AssetMaintenance.AssetMaintenanceSchedules import AssetMaintenanceSchedule
from apps.assets.models.AssetPerformance.AssetEnergyReadings import AssetEnergyReading
from apps.assets.models.SpaceFacilityAsset.AssetBuildingSystems import AssetBuildingSystem
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset


class AssetBuildingSystemForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit form for HVAC, electrical, plumbing, elevator, fire, and structural systems."""

    _TENANT_FK_MAP = {
        "facility_space": AssetFacilitySpace,
        "operational_asset": Asset,
        "fixed_asset": FixedAsset,
        "latest_energy_reading": AssetEnergyReading,
        "maintenance_schedule": AssetMaintenanceSchedule,
        "operating_permit": AssetPermitLicense,
        "schematic_document": AssetDocument,
        "service_vendor": Party,
        "org_unit": OrgUnit,
    }

    class Meta:
        model = AssetBuildingSystem
        fields = [
            "name",
            "system_domain",
            "subsystem_type",
            "facility_space",
            "pin_x_pct",
            "pin_y_pct",
            "manufacturer",
            "model_number",
            "serial_number",
            "load_or_voltage_rating",
            "ashrae_nfpa_code_ref",
            "served_area_sqft",
            "design_capacity_btu_kw",
            "refrigerant_type",
            "setpoint_temp_c",
            "measured_temp_c",
            "target_humidity_pct",
            "measured_humidity_pct",
            "airflow_cfm",
            "energy_efficiency_rating",
            "condition_grade",
            "criticality_tier",
            "remaining_useful_life_years",
            "replacement_cost_estimate",
            "last_statutory_inspection_date",
            "next_inspection_due_date",
            "operational_asset",
            "fixed_asset",
            "latest_energy_reading",
            "maintenance_schedule",
            "operating_permit",
            "schematic_document",
            "service_vendor",
            "org_unit",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Rooftop AHU-01 North"}),
            "system_domain": forms.Select(attrs={"class": "form-select"}),
            "subsystem_type": forms.Select(attrs={"class": "form-select"}),
            "facility_space": forms.Select(attrs={"class": "form-select"}),
            "pin_x_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "pin_y_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "manufacturer": forms.TextInput(attrs={"class": "form-input"}),
            "model_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "load_or_voltage_rating": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 480V 3-Phase / 2500 kg"}),
            "ashrae_nfpa_code_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ASHRAE 90.1 / NFPA 72"}),
            "served_area_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "design_capacity_btu_kw": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "refrigerant_type": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. R-410A / R-134a"}),
            "setpoint_temp_c": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "measured_temp_c": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "target_humidity_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "measured_humidity_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "airflow_cfm": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "energy_efficiency_rating": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. SEER 18 / IE3"}),
            "condition_grade": forms.Select(attrs={"class": "form-select"}),
            "criticality_tier": forms.Select(attrs={"class": "form-select"}),
            "remaining_useful_life_years": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "replacement_cost_estimate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "last_statutory_inspection_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_inspection_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "latest_energy_reading": forms.Select(attrs={"class": "form-select"}),
            "maintenance_schedule": forms.Select(attrs={"class": "form-select"}),
            "operating_permit": forms.Select(attrs={"class": "form-select"}),
            "schematic_document": forms.Select(attrs={"class": "form-select"}),
            "service_vendor": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FK_MAP)
        if "latest_energy_reading" in self.fields and self.tenant is not None:
            self.fields["latest_energy_reading"].queryset = self.fields[
                "latest_energy_reading"
            ].queryset.select_related("fixed_asset", "operational_asset")
        if "schematic_document" in self.fields and self.tenant is not None:
            self.fields["schematic_document"].queryset = self.fields[
                "schematic_document"
            ].queryset.filter(readable_asset_document_q(self.user))

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FK_MAP.keys()))

        doc = cleaned.get("schematic_document")
        if doc is not None and not is_asset_document_readable(doc, self.user):
            self.add_error(
                "schematic_document",
                "You do not have permission to reference this restricted document.",
            )

        for fld, label in (
            ("pin_x_pct", "Pin X %"),
            ("pin_y_pct", "Pin Y %"),
            ("target_humidity_pct", "Target humidity %"),
            ("measured_humidity_pct", "Measured humidity %"),
        ):
            val = cleaned.get(fld)
            if val is not None and (val < Decimal("0.00") or val > Decimal("100.00")):
                self.add_error(fld, f"{label} must be between 0 and 100.")

        for fld, label in (
            ("served_area_sqft", "Served area"),
            ("design_capacity_btu_kw", "Design capacity"),
            ("airflow_cfm", "Airflow CFM"),
            ("replacement_cost_estimate", "Replacement cost estimate"),
        ):
            val = cleaned.get(fld)
            if val is not None and val < Decimal("0.00"):
                self.add_error(fld, f"{label} cannot be negative.")

        last_insp = cleaned.get("last_statutory_inspection_date")
        next_insp = cleaned.get("next_inspection_due_date")
        if last_insp and next_insp and next_insp < last_insp:
            self.add_error(
                "next_inspection_due_date",
                "Next inspection due date cannot precede the last statutory inspection date.",
            )
        return cleaned
