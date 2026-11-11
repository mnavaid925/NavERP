from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.assets.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    reject_foreign,
)
from apps.assets.models.IntegrationApiHub._validators import validate_json_object
from apps.assets.models.IntegrationApiHub.AssetGisMappings import (
    AssetGisMapping,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)
from apps.core.models import OrgUnit
from apps.scm.models import Asset, Location

User = get_user_model()


class AssetGisMappingForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Asset GIS Spatial Mappings with coordinate & LRS checks."""

    class Meta:
        model = AssetGisMapping
        fields = [
            "connector",
            "operational_asset",
            "location",
            "org_unit",
            "external_feature_id",
            "layer_name",
            "geometry_type",
            "coordinate_system_srid",
            "latitude",
            "longitude",
            "elevation_meters",
            "is_linear_asset",
            "lrs_route_id",
            "lrs_from_measure",
            "lrs_to_measure",
            "lrs_measure_unit",
            "geojson_payload",
            "system_of_record",
            "sync_direction",
            "drift_status",
            "status",
            "gis_custodian",
            "notes",
        ]
        widgets = {
            "connector": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "location": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "external_feature_id": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. ARCGIS-SUB-10482 or GIS-PIPE-044",
                }
            ),
            "layer_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. transmission_substations_pt or pipeline_corridor",
                }
            ),
            "geometry_type": forms.Select(attrs={"class": "form-select"}),
            "coordinate_system_srid": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
            "latitude": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.000001"}
            ),
            "longitude": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.000001"}
            ),
            "elevation_meters": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01"}
            ),
            "is_linear_asset": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "lrs_route_id": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. ROUTE-I95-SEG4"}
            ),
            "lrs_from_measure": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.001"}
            ),
            "lrs_to_measure": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.001"}
            ),
            "lrs_measure_unit": forms.Select(attrs={"class": "form-select"}),
            "geojson_payload": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 3,
                    "placeholder": '{"type": "Point", "coordinates": [-73.9857, 40.7484]}',
                }
            ),
            "system_of_record": forms.Select(attrs={"class": "form-select"}),
            "sync_direction": forms.Select(attrs={"class": "form-select"}),
            "drift_status": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "gis_custodian": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["connector"].queryset = (
                AssetIntegrationConnector.objects.filter(
                    tenant=self.tenant
                ).order_by("number")
            )
            self.fields["operational_asset"].queryset = Asset.objects.filter(
                tenant=self.tenant
            ).order_by("code")
            self.fields["location"].queryset = Location.objects.filter(
                tenant=self.tenant
            ).order_by("code")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["gis_custodian"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
        else:
            for fk_field in (
                "connector",
                "operational_asset",
                "location",
                "org_unit",
                "gis_custodian",
            ):
                self.fields[fk_field].queryset = self.fields[fk_field].queryset.model.objects.none()

        for optional_field in (
            "operational_asset",
            "location",
            "org_unit",
            "latitude",
            "longitude",
            "elevation_meters",
            "lrs_route_id",
            "lrs_from_measure",
            "lrs_to_measure",
            "geojson_payload",
            "gis_custodian",
            "notes",
        ):
            self.fields[optional_field].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "connector",
                "operational_asset",
                "location",
                "org_unit",
                "gis_custodian",
            ],
        )

        lat = cleaned_data.get("latitude")
        lon = cleaned_data.get("longitude")
        if lat is not None and (lat < Decimal("-90") or lat > Decimal("90")):
            self.add_error("latitude", "Latitude must be between -90 and 90 degrees.")
        if lon is not None and (lon < Decimal("-180") or lon > Decimal("180")):
            self.add_error(
                "longitude", "Longitude must be between -180 and 180 degrees."
            )

        srid = cleaned_data.get("coordinate_system_srid")
        if srid is not None and srid < 1:
            self.add_error(
                "coordinate_system_srid", "Coordinate SRID must be a positive integer."
            )

        lrs_from = cleaned_data.get("lrs_from_measure")
        lrs_to = cleaned_data.get("lrs_to_measure")
        if lrs_from is not None and lrs_to is not None and lrs_to < lrs_from:
            self.add_error(
                "lrs_to_measure",
                "LRS end measure must be greater than or equal to start measure.",
            )

        try:
            validate_json_object(
                cleaned_data.get("geojson_payload"),
                field_label="GeoJSON payload",
            )
        except ValidationError as exc:
            self.add_error("geojson_payload", exc)

        return cleaned_data
