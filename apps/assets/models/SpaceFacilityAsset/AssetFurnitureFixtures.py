"""Furniture, Fixtures & Equipment (FF&E) + IMAC tracking model (11.17)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered
from apps.assets.models.SpaceFacilityAsset._validators import (
    add_field_error,
    validate_non_negative,
    validate_pct_range,
    validate_tenant_fks,
)


class AssetFurnitureFixture(TenantNumbered):
    """Furniture, Fixtures & Equipment (FF&E) & Install/Move/Add/Change (IMAC) register [AFFE]."""

    NUMBER_PREFIX = "AFFE"

    FFE_CATEGORY_CHOICES = [
        ("workstation_desk", "Workstation / Desk"),
        ("ergonomic_seating", "Ergonomic Seating"),
        ("conference_table", "Conference / Boardroom Table"),
        ("modular_partition", "Modular Partition / Panel"),
        ("storage_cabinet", "Filing / Storage Cabinet"),
        ("av_display_fixture", "AV Display / Smartboard"),
        ("lighting_fixture", "Architectural Lighting Fixture"),
        ("lab_casework", "Lab Bench / Casework"),
        ("reception_millwork", "Reception / Custom Millwork"),
    ]

    CONDITION_GRADE_CHOICES = [
        ("new", "New"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("worn", "Worn"),
        ("damaged", "Damaged"),
    ]

    MOVE_STATUS_CHOICES = [
        ("in_place", "In Place"),
        ("move_requested", "Move Requested"),
        ("scheduled_reconfig", "Scheduled Reconfiguration"),
        ("in_transit", "In Transit"),
        ("relocated", "Relocated"),
        ("in_storage", "In Storage"),
        ("retired", "Retired"),
    ]

    MOVE_STATUS_CSS = {
        "in_place": "badge-green",
        "move_requested": "badge-amber",
        "scheduled_reconfig": "badge-info",
        "in_transit": "badge-amber",
        "relocated": "badge-green",
        "in_storage": "badge-slate",
        "retired": "badge-muted",
    }

    CONDITION_CSS = {
        "new": "badge-green",
        "good": "badge-info",
        "fair": "badge-amber",
        "worn": "badge-amber",
        "damaged": "badge-red",
    }

    LOCKED_STATUSES = {"retired"}

    _TENANT_FK_FIELDS = (
        "facility_space",
        "target_space",
        "custodian_party",
        "assigned_org_unit",
        "operational_asset",
        "fixed_asset",
        "movement_log",
        "move_coordinator",
    )

    name = models.CharField(max_length=200)
    ffe_category = models.CharField(
        max_length=32,
        choices=FFE_CATEGORY_CHOICES,
        default="workstation_desk",
    )
    asset_tag_code = models.CharField(max_length=64, blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    model_sku = models.CharField(max_length=80, blank=True)
    finish_material = models.CharField(max_length=80, blank=True)

    facility_space = models.ForeignKey(
        "assets.AssetFacilitySpace",
        on_delete=models.PROTECT,
        related_name="furniture_fixtures",
    )
    target_space = models.ForeignKey(
        "assets.AssetFacilitySpace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_furniture_fixtures",
    )
    custodian_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodied_furniture_fixtures",
    )
    assigned_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="furniture_fixtures",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="furniture_fixtures",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="furniture_fixtures",
    )
    movement_log = models.ForeignKey(
        "assets.AssetMovementLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="furniture_fixture_moves",
    )
    move_coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coordinated_ffe_moves",
    )

    quantity = models.PositiveIntegerField(default=1)
    unit_replacement_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    pin_x_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pin_y_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    condition_grade = models.CharField(
        max_length=20,
        choices=CONDITION_GRADE_CHOICES,
        default="good",
    )
    move_status = models.CharField(
        max_length=28,
        choices=MOVE_STATUS_CHOICES,
        default="in_place",
        editable=False,
    )
    reconfiguration_batch_ref = models.CharField(max_length=64, blank=True)
    move_scheduled_date = models.DateField(null=True, blank=True)
    move_completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    estimated_move_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    move_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["facility_space", "name", "-number"]
        verbose_name = "Furniture & Fixture"
        verbose_name_plural = "Furniture & Fixtures"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_affe_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "move_status"], name="idx_affe_ten_mstat"),
            models.Index(fields=["tenant", "ffe_category"], name="idx_affe_ten_cat"),
            models.Index(fields=["tenant", "facility_space"], name="idx_affe_ten_spc"),
            models.Index(fields=["tenant", "reconfiguration_batch_ref"], name="idx_affe_ten_batch"),
        ]

    @property
    def total_replacement_value(self):
        qty = Decimal(str(self.quantity or 0))
        unit_cost = self.unit_replacement_cost or Decimal("0.00")
        return (qty * unit_cost).quantize(Decimal("0.01"))

    @property
    def is_locked(self):
        return self.move_status in self.LOCKED_STATUSES

    @property
    def move_status_badge_class(self):
        return self.MOVE_STATUS_CSS.get(self.move_status, "badge-slate")

    @property
    def condition_badge_class(self):
        return self.CONDITION_CSS.get(self.condition_grade, "badge-slate")

    def clean(self):
        super().clean()
        errors = {}
        if self.tenant_id:
            validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)

        if self.quantity is not None and self.quantity < 1:
            add_field_error(errors, "quantity", "Quantity must be at least 1.")

        if self.target_space_id and self.facility_space_id and self.target_space_id == self.facility_space_id:
            add_field_error(
                errors,
                "target_space",
                "Target space must differ from the current assigned facility space.",
            )

        validate_pct_range(self.pin_x_pct, errors, "pin_x_pct", "Pin X %")
        validate_pct_range(self.pin_y_pct, errors, "pin_y_pct", "Pin Y %")
        validate_non_negative(
            self.unit_replacement_cost,
            errors,
            "unit_replacement_cost",
            "Unit replacement cost",
        )
        validate_non_negative(
            self.estimated_move_cost,
            errors,
            "estimated_move_cost",
            "Estimated move cost",
        )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.number} — {self.name}"
