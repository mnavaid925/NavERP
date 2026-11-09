from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetModel(TenantNumbered):
    """Manufacturer equipment model blueprint, technical specs, warranty template, and meter baseline [AMOD-]."""

    NUMBER_PREFIX = "AMOD"

    WARRANTY_COVERAGE_CHOICES = [
        ("full_parts_labor", "Full Warranty (Parts & Labor)"),
        ("parts_only", "Parts Only"),
        ("powertrain_only", "Powertrain / Core Component Only"),
        ("limited", "Limited Commercial Warranty"),
        ("no_warranty", "As-Is / No Warranty"),
    ]

    MODEL_STATUS_CHOICES = [
        ("active", "Active Production"),
        ("phased_out", "Phased Out / Legacy"),
        ("discontinued", "Discontinued / Obsolete"),
        ("draft", "Draft Engineering"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "phased_out": "badge-amber",
        "discontinued": "badge-red",
        "draft": "badge-slate",
    }

    model_number = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Manufacturer catalog or engineering model identifier, e.g. CAT-320GC, CVHE-500",
    )
    name = models.CharField(
        max_length=200,
        help_text="Commercial model name or equipment series, e.g. 320 GC Hydraulic Excavator",
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.PROTECT,
        related_name="models",
        help_text="Standard asset category taxonomy node",
    )
    manufacturer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_models",
        help_text="Original Equipment Manufacturer (OEM) vendor record",
    )
    manufacturer_name_fallback = models.CharField(
        max_length=120,
        blank=True,
        help_text="Fallback manufacturer text if party master record is not linked",
    )

    description = models.TextField(blank=True, help_text="Equipment description, design parameters, and features")

    standard_warranty_months = models.PositiveIntegerField(
        default=12,
        help_text="Default manufacturer warranty term in months from commissioning",
    )
    warranty_coverage_type = models.CharField(
        max_length=24,
        choices=WARRANTY_COVERAGE_CHOICES,
        default="full_parts_labor",
    )
    expected_useful_life_months = models.PositiveIntegerField(
        default=60,
        help_text="Expected operational operating lifespan in months",
    )

    default_meter_name = models.CharField(
        max_length=40,
        blank=True,
        help_text="Primary operating meter, e.g. Operating Hours, Odometer, Stroke Count",
    )
    default_meter_unit = models.CharField(
        max_length=16,
        blank=True,
        help_text="Meter unit, e.g. h, km, cycles",
    )

    estimated_replacement_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Current benchmark replacement cost for like-for-like asset renewal",
    )
    model_status = models.CharField(
        max_length=20,
        choices=MODEL_STATUS_CHOICES,
        default="active",
        help_text="Commercial production status",
    )
    technical_specifications = models.TextField(
        blank=True,
        help_text="Baseline technical specifications (capacity, horsepower, voltage, throughput)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this model is available for assignment to physical assets",
    )

    class Meta:
        db_table = "assets_model"
        ordering = ["model_number"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "model_number"], name="assets_amod_ten_modnum_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_amod_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category"], name="idx_amod_ten_cat"),
            models.Index(fields=["tenant", "manufacturer"], name="idx_amod_ten_mfr"),
            models.Index(fields=["tenant", "model_status"], name="idx_amod_ten_status"),
        ]

    def __str__(self):
        return f"{self.model_number} — {self.name}"

    def clean(self):
        super().clean()
        if self.model_number:
            self.model_number = self.model_number.strip().upper()

    @property
    def display_manufacturer(self):
        if self.manufacturer:
            return self.manufacturer.name
        return self.manufacturer_name_fallback or "—"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.model_status, "badge-slate")
