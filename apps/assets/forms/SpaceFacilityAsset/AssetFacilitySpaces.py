"""Forms for AssetFacilitySpace (11.17 Space & Facility Asset Management)."""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.SpaceFacilityAsset._helpers import (
    scope_tenant_querysets,
    validate_safe_floor_plan_upload,
)
from apps.assets.models.AssetDocumentKnowledge._validators import (
    is_asset_document_readable,
    readable_asset_document_q,
)
from apps.assets.models.AssetDocumentKnowledge.AssetDocuments import AssetDocument
from apps.assets.models.IntegrationApiHub.AssetGisMappings import AssetGisMapping
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.core.models import OrgUnit
from apps.scm.models import Location

User = get_user_model()


class AssetFacilitySpaceForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit form for architectural spaces, BOMA metrics, and CAD/BIM refs."""

    _TENANT_FK_MAP = {
        "parent": AssetFacilitySpace,
        "org_unit": OrgUnit,
        "scm_location": Location,
        "gis_mapping": AssetGisMapping,
        "floor_plan_document": AssetDocument,
        "space_steward": User,
    }

    class Meta:
        model = AssetFacilitySpace
        fields = [
            "code",
            "name",
            "space_level",
            "space_category",
            "parent",
            "org_unit",
            "scm_location",
            "gis_mapping",
            "floor_plan_document",
            "space_steward",
            "gross_area_sqft",
            "rentable_area_sqft",
            "usable_area_sqft",
            "common_area_sqft",
            "annual_rate_per_sqft",
            "design_seat_capacity",
            "current_headcount",
            "cad_layer_ref",
            "bim_guid",
            "bim_level_ref",
            "drawing_revision",
            "floor_plan_image",
            "notes",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. HQ-F2-R204"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Space / Room Name"}),
            "space_level": forms.Select(attrs={"class": "form-select"}),
            "space_category": forms.Select(attrs={"class": "form-select"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "scm_location": forms.Select(attrs={"class": "form-select"}),
            "gis_mapping": forms.Select(attrs={"class": "form-select"}),
            "floor_plan_document": forms.Select(attrs={"class": "form-select"}),
            "space_steward": forms.Select(attrs={"class": "form-select"}),
            "gross_area_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "rentable_area_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "usable_area_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "common_area_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "annual_rate_per_sqft": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "design_seat_capacity": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "current_headcount": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "cad_layer_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "A-AREA-IDEN"}),
            "bim_guid": forms.TextInput(attrs={"class": "form-input", "placeholder": "IFC GlobalId / Revit GUID"}),
            "bim_level_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "Level 02"}),
            "drawing_revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "Rev C"}),
            "floor_plan_image": forms.ClearableFileInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FK_MAP)
        if "floor_plan_document" in self.fields and self.tenant is not None:
            self.fields["floor_plan_document"].queryset = self.fields[
                "floor_plan_document"
            ].queryset.filter(readable_asset_document_q(self.user))

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("Space code is required.")
        return code

    def clean_floor_plan_image(self):
        return validate_safe_floor_plan_upload(self.cleaned_data.get("floor_plan_image"))

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, list(self._TENANT_FK_MAP.keys()))

        doc = cleaned.get("floor_plan_document")
        if doc is not None and not is_asset_document_readable(doc, self.user):
            self.add_error(
                "floor_plan_document",
                "You do not have permission to reference this restricted document.",
            )

        parent = cleaned.get("parent")
        if parent is not None and self.instance.pk and parent.pk == self.instance.pk:
            self.add_error("parent", "A facility space cannot be its own parent.")

        for fld, label in (
            ("gross_area_sqft", "Gross area"),
            ("rentable_area_sqft", "Rentable area"),
            ("usable_area_sqft", "Usable area"),
            ("common_area_sqft", "Common area"),
            ("annual_rate_per_sqft", "Annual rate per sqft"),
        ):
            val = cleaned.get(fld)
            if val is not None and val < Decimal("0.00"):
                self.add_error(fld, f"{label} cannot be negative.")
        return cleaned
