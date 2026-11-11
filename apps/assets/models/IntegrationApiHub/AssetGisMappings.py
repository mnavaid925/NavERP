from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from ._validators import validate_json_object, validate_tenant_fks

from apps.assets.models._base import TenantNumbered


class AssetGisMapping(TenantNumbered):
    """
    GIS and spatial asset mapping linking operational assets and storage/facility
    locations with Esri ArcGIS, QGIS/PostGIS feature layers, GPS coordinates, and
    Linear Referencing System (LRS) corridors.
    """

    NUMBER_PREFIX = "AGIS"

    GEOMETRY_TYPE_CHOICES = [
        ("point", "Point"),
        ("linestring", "LineString"),
        ("polygon", "Polygon"),
        ("multipoint", "MultiPoint"),
    ]

    LRS_UNIT_CHOICES = [
        ("meters", "Meters"),
        ("km", "Kilometers"),
        ("miles", "Miles"),
        ("feet", "Feet"),
    ]

    SYSTEM_OF_RECORD_CHOICES = [
        ("gis_authoritative", "GIS Authoritative"),
        ("erp_authoritative", "ERP Authoritative"),
        ("shared_field", "Shared Field"),
    ]

    SYNC_DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]

    DRIFT_STATUS_CHOICES = [
        ("in_sync", "In Sync"),
        ("location_drift", "Location Drift"),
        ("attribute_drift", "Attribute Drift"),
        ("unverified", "Unverified"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("archived", "Archived"),
    ]

    DRIFT_BADGE_MAP = {
        "in_sync": "badge-green",
        "location_drift": "badge-red",
        "attribute_drift": "badge-amber",
        "unverified": "badge-slate",
    }

    STATUS_BADGE_MAP = {
        "active": "badge-green",
        "paused": "badge-amber",
        "archived": "badge-muted",
    }

    connector = models.ForeignKey(
        "assets.AssetIntegrationConnector",
        on_delete=models.PROTECT,
        related_name="gis_mappings",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gis_mappings",
    )
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gis_mappings",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gis_mappings",
    )

    external_feature_id = models.CharField(max_length=120)
    layer_name = models.CharField(max_length=120)
    geometry_type = models.CharField(
        max_length=20, choices=GEOMETRY_TYPE_CHOICES, default="point"
    )
    coordinate_system_srid = models.PositiveIntegerField(default=4326)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    elevation_meters = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True
    )

    is_linear_asset = models.BooleanField(default=False)
    lrs_route_id = models.CharField(max_length=80, blank=True)
    lrs_from_measure = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    lrs_to_measure = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    lrs_measure_unit = models.CharField(
        max_length=16, choices=LRS_UNIT_CHOICES, default="km"
    )

    geojson_payload = models.TextField(blank=True)
    system_of_record = models.CharField(
        max_length=24, choices=SYSTEM_OF_RECORD_CHOICES, default="erp_authoritative"
    )
    sync_direction = models.CharField(
        max_length=20, choices=SYNC_DIRECTION_CHOICES, default="bidirectional"
    )
    drift_status = models.CharField(
        max_length=24,
        choices=DRIFT_STATUS_CHOICES,
        default="unverified",
        editable=False,
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )
    last_spatial_sync_at = models.DateTimeField(null=True, blank=True, editable=False)
    gis_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_gis_mappings",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Asset GIS Mapping"
        verbose_name_plural = "Asset GIS Mappings"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_agis_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "operational_asset"],
                name="idx_agis_ten_asset",
            ),
            models.Index(
                fields=["tenant", "drift_status"],
                name="idx_agis_ten_drift",
            ),
            models.Index(
                fields=["tenant", "status"],
                name="idx_agis_ten_stat",
            ),
            models.Index(
                fields=["tenant", "connector"],
                name="idx_agis_ten_conn",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.layer_name} / {self.external_feature_id}"

    @property
    def drift_badge_class(self):
        return self.DRIFT_BADGE_MAP.get(self.drift_status, "badge-slate")

    @property
    def status_badge_class(self):
        return self.STATUS_BADGE_MAP.get(self.status, "badge-slate")

    def compute_spatial_drift_status(self):
        """Evaluate spatial completeness and asset linkage without mutating DB state."""
        has_point = self.latitude is not None and self.longitude is not None
        has_lrs = self.is_linear_asset and bool((self.lrs_route_id or "").strip())
        has_geojson = bool((self.geojson_payload or "").strip())
        if not (has_point or has_lrs or has_geojson):
            return "location_drift"
        if self.operational_asset_id is None and self.location_id is None:
            return "attribute_drift"
        return "in_sync"

    def clean(self):
        super().clean()
        errors = {}
        if self.latitude is not None and (
            self.latitude < Decimal("-90") or self.latitude > Decimal("90")
        ):
            errors["latitude"] = "Latitude must be between -90 and 90 degrees."
        if self.longitude is not None and (
            self.longitude < Decimal("-180") or self.longitude > Decimal("180")
        ):
            errors["longitude"] = "Longitude must be between -180 and 180 degrees."
        if (
            self.coordinate_system_srid is not None
            and self.coordinate_system_srid < 1
        ):
            errors["coordinate_system_srid"] = "Coordinate SRID must be a positive integer."
        if (
            self.lrs_from_measure is not None
            and self.lrs_to_measure is not None
            and self.lrs_to_measure < self.lrs_from_measure
        ):
            errors["lrs_to_measure"] = (
                "LRS end measure must be greater than or equal to start measure."
            )
        try:
            validate_json_object(
                self.geojson_payload, field_label="GeoJSON payload"
            )
        except ValidationError as exc:
            errors["geojson_payload"] = exc.messages
        validate_tenant_fks(
            self,
            errors,
            (
                "connector",
                "operational_asset",
                "location",
                "org_unit",
                "gis_custodian",
            ),
        )
        if errors:
            raise ValidationError(errors)
