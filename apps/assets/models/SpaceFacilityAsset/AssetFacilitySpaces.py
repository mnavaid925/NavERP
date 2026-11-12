"""Facility Space & Floor Plan Mapping model (11.17)."""

from decimal import Decimal, ROUND_HALF_UP
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered
from apps.assets.models.SpaceFacilityAsset._validators import (
    add_field_error,
    validate_non_negative,
    validate_space_parent_cycle,
    validate_tenant_fks,
)


class AssetFacilitySpace(TenantNumbered):
    """Architectural facility space hierarchy, BOMA area metrics, CAD/BIM mapping, and utilization [AFSP]."""

    NUMBER_PREFIX = "AFSP"

    SPACE_LEVEL_CHOICES = [
        ("building", "Building / Structure"),
        ("floor", "Floor / Level"),
        ("wing_zone", "Wing / Fire Zone"),
        ("room", "Room / Suite"),
        ("mechanical_bay", "Mechanical / Utility Bay"),
        ("exterior_pad", "Exterior Pad / Yard"),
    ]

    SPACE_CATEGORY_CHOICES = [
        ("office_workspace", "Office / Workstation"),
        ("conference_meeting", "Conference / Meeting"),
        ("mechanical_room", "Mechanical / Plant Room"),
        ("electrical_closet", "Electrical / Switchgear Room"),
        ("hvac_zone", "HVAC Thermal Zone"),
        ("cleanroom_lab", "Cleanroom / Laboratory"),
        ("lobby_common", "Lobby / Common Area"),
        ("server_idf_room", "Server / IDF / MDF Room"),
        ("warehouse_bay", "Warehouse / Storage Bay"),
        ("restroom_utility", "Restroom / Core Utility"),
    ]

    OCCUPANCY_STATUS_CHOICES = [
        ("occupied", "Occupied"),
        ("underutilized", "Underutilized"),
        ("vacant", "Vacant"),
        ("reserved_reconfig", "Reserved for Reconfig"),
        ("offline", "Offline / Renovation"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("planned", "Planned"),
        ("under_renovation", "Under Renovation"),
        ("decommissioned", "Decommissioned"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "planned": "badge-info",
        "under_renovation": "badge-amber",
        "decommissioned": "badge-muted",
    }

    OCCUPANCY_CSS = {
        "occupied": "badge-green",
        "underutilized": "badge-amber",
        "vacant": "badge-info",
        "reserved_reconfig": "badge-slate",
        "offline": "badge-red",
    }

    SPACE_LEVEL_CSS = {
        "building": "badge-info",
        "floor": "badge-slate",
        "wing_zone": "badge-slate",
        "room": "badge-green",
        "mechanical_bay": "badge-amber",
        "exterior_pad": "badge-muted",
    }

    EDITABLE_STATUSES = {"planned", "active", "under_renovation"}
    LOCKED_STATUSES = {"decommissioned"}

    _TENANT_FK_FIELDS = (
        "parent",
        "org_unit",
        "scm_location",
        "gis_mapping",
        "floor_plan_document",
        "space_steward",
    )

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    space_level = models.CharField(
        max_length=24, choices=SPACE_LEVEL_CHOICES, default="room"
    )
    space_category = models.CharField(
        max_length=32, choices=SPACE_CATEGORY_CHOICES, default="office_workspace"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_spaces",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_spaces",
    )
    scm_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_spaces",
    )
    gis_mapping = models.ForeignKey(
        "assets.AssetGisMapping",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_spaces",
    )
    floor_plan_document = models.ForeignKey(
        "assets.AssetDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_spaces",
    )
    space_steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stewarded_facility_spaces",
    )

    gross_area_sqft = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    rentable_area_sqft = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    usable_area_sqft = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    common_area_sqft = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    annual_rate_per_sqft = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    design_seat_capacity = models.PositiveIntegerField(default=0)
    current_headcount = models.PositiveIntegerField(default=0)
    occupancy_status = models.CharField(
        max_length=24,
        choices=OCCUPANCY_STATUS_CHOICES,
        default="vacant",
        editable=False,
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="active",
        editable=False,
    )

    cad_layer_ref = models.CharField(max_length=100, blank=True)
    bim_guid = models.CharField(max_length=64, blank=True)
    bim_level_ref = models.CharField(max_length=64, blank=True)
    drawing_revision = models.CharField(max_length=24, blank=True)
    floor_plan_image = models.FileField(
        upload_to="assets/space_floor_plans/%Y/%m/",
        blank=True,
        null=True,
    )
    original_floor_plan_name = models.CharField(
        max_length=255, blank=True, editable=False
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code", "name", "-number"]
        verbose_name = "Facility Space"
        verbose_name_plural = "Facility Spaces"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_afsp_ten_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="assets_afsp_ten_code_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_afsp_ten_stat"),
            models.Index(fields=["tenant", "space_level"], name="idx_afsp_ten_lvl"),
            models.Index(fields=["tenant", "space_category"], name="idx_afsp_ten_cat"),
            models.Index(fields=["tenant", "occupancy_status"], name="idx_afsp_ten_occ"),
            models.Index(fields=["tenant", "parent"], name="idx_afsp_ten_par"),
        ]

    @property
    def utilization_pct(self):
        cap = self.design_seat_capacity or 0
        if cap <= 0:
            return Decimal("0.00")
        head = self.current_headcount or 0
        return ((Decimal(head) / Decimal(cap)) * Decimal("100.00")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def annual_space_cost(self):
        area = self.rentable_area_sqft or Decimal("0.00")
        if area <= Decimal("0.00"):
            area = self.usable_area_sqft or Decimal("0.00")
        rate = self.annual_rate_per_sqft or Decimal("0.00")
        return (area * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def occupancy_badge_class(self):
        return self.OCCUPANCY_CSS.get(self.occupancy_status, "badge-slate")

    @property
    def level_badge_class(self):
        return self.SPACE_LEVEL_CSS.get(self.space_level, "badge-slate")

    def compute_occupancy_status(self):
        if self.status in ("under_renovation", "decommissioned"):
            return "offline"
        head = self.current_headcount or 0
        cap = self.design_seat_capacity or 0
        if head == 0:
            return "vacant"
        if cap > 0 and self.utilization_pct < Decimal("50.00"):
            return "underutilized"
        return "occupied"

    def clean(self):
        super().clean()
        errors = {}
        self.code = (self.code or "").strip().upper()
        if not self.code:
            add_field_error(errors, "code", "Space code is required.")

        if self.tenant_id:
            validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)
        validate_space_parent_cycle(self, errors)

        validate_non_negative(self.gross_area_sqft, errors, "gross_area_sqft", "Gross area")
        validate_non_negative(self.rentable_area_sqft, errors, "rentable_area_sqft", "Rentable area")
        validate_non_negative(self.usable_area_sqft, errors, "usable_area_sqft", "Usable area")
        validate_non_negative(self.common_area_sqft, errors, "common_area_sqft", "Common area")
        validate_non_negative(self.annual_rate_per_sqft, errors, "annual_rate_per_sqft", "Annual rate per sqft")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        self.occupancy_status = self.compute_occupancy_status()
        if self.floor_plan_image and getattr(self.floor_plan_image, "name", ""):
            self.original_floor_plan_name = os.path.basename(str(self.floor_plan_image.name))[:255]
        elif not self.floor_plan_image:
            self.original_floor_plan_name = ""
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} — {self.code} {self.name}".strip()
