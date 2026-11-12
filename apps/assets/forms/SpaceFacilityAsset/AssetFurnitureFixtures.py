"""Forms for AssetFurnitureFixture (11.17 Furniture & Fixture Tracking / IMAC)."""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.SpaceFacilityAsset._helpers import scope_tenant_querysets
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.models.SpaceFacilityAsset.AssetFurnitureFixtures import AssetFurnitureFixture
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset

User = get_user_model()


class AssetFurnitureFixtureForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit form for FF&E inventory, pin coordinates, and IMAC move planning."""

    _TENANT_FK_MAP = {
        "facility_space": AssetFacilitySpace,
        "target_space": AssetFacilitySpace,
        "custodian_party": Party,
        "assigned_org_unit": OrgUnit,
        "operational_asset": Asset,
        "fixed_asset": FixedAsset,
        "move_coordinator": User,
    }

    class Meta:
        model = AssetFurnitureFixture
        fields = [
            "name",
            "ffe_category",
            "asset_tag_code",
            "manufacturer",
            "model_sku",
            "finish_material",
            "facility_space",
            "target_space",
            "custodian_party",
            "assigned_org_unit",
            "operational_asset",
            "fixed_asset",
            "move_coordinator",
            "quantity",
            "unit_replacement_cost",
            "pin_x_pct",
            "pin_y_pct",
            "condition_grade",
            "reconfiguration_batch_ref",
            "move_scheduled_date",
            "estimated_move_cost",
            "move_notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Herman Miller Sit-Stand Cluster"}),
            "ffe_category": forms.Select(attrs={"class": "form-select"}),
            "asset_tag_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "Barcode / RFID tag"}),
            "manufacturer": forms.TextInput(attrs={"class": "form-input", "placeholder": "Herman Miller / Steelcase"}),
            "model_sku": forms.TextInput(attrs={"class": "form-input", "placeholder": "Model / SKU"}),
            "finish_material": forms.TextInput(attrs={"class": "form-input", "placeholder": "Walnut / Graphite Mesh"}),
            "facility_space": forms.Select(attrs={"class": "form-select"}),
            "target_space": forms.Select(attrs={"class": "form-select"}),
            "custodian_party": forms.Select(attrs={"class": "form-select"}),
            "assigned_org_unit": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "move_coordinator": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "unit_replacement_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "pin_x_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "pin_y_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "condition_grade": forms.Select(attrs={"class": "form-select"}),
            "reconfiguration_batch_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "IMAC-2026-Q4"}),
            "move_scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "estimated_move_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "move_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FK_MAP)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FK_MAP.keys()))

        facility_space = cleaned.get("facility_space")
        target_space = cleaned.get("target_space")
        if facility_space is not None and target_space is not None and facility_space.pk == target_space.pk:
            self.add_error("target_space", "Target space must differ from the current assigned space.")

        qty = cleaned.get("quantity")
        if qty is not None and qty < 1:
            self.add_error("quantity", "Quantity must be at least 1.")

        for pct_field, label in (("pin_x_pct", "Pin X %"), ("pin_y_pct", "Pin Y %")):
            val = cleaned.get(pct_field)
            if val is not None and (val < Decimal("0.00") or val > Decimal("100.00")):
                self.add_error(pct_field, f"{label} must be between 0 and 100.")

        for cost_field, label in (
            ("unit_replacement_cost", "Unit replacement cost"),
            ("estimated_move_cost", "Estimated move cost"),
        ):
            val = cleaned.get(cost_field)
            if val is not None and val < Decimal("0.00"):
                self.add_error(cost_field, f"{label} cannot be negative.")

        return cleaned
