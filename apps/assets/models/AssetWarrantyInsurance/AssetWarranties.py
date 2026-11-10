from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetWarranty(TenantNumbered):
    """
    Asset warranty and extended protection contract [AWAR-].
    Captures OEM standard warranties, extended coverage contracts, dual thresholds
    (calendar end date + machine operating hours/km meter limit), parts/labor coverage %,
    deductible terms, and warrantor/vendor provider details.
    """

    NUMBER_PREFIX = "AWAR"

    WARRANTY_TYPE_CHOICES = [
        ("oem_standard", "OEM Factory Standard Warranty"),
        ("oem_extended", "OEM Extended Warranty"),
        ("third_party_extended", "Third-Party Service Contract / Warranty"),
        ("dealer_certified", "Dealer Certified Pre-Owned Warranty"),
        ("refurbished_component", "Rebuilt / Refurbished Component Warranty"),
    ]

    COVERAGE_SCOPE_CHOICES = [
        ("comprehensive", "Comprehensive (Bumper-to-Bumper)"),
        ("parts_and_labor", "Parts and Labor Included"),
        ("parts_only", "Parts Only (Labor Excluded)"),
        ("powertrain_major_components", "Powertrain & Major Subsystems"),
        ("corrosion_structural", "Structural Integrity & Corrosion"),
    ]

    METER_TYPE_CHOICES = [
        ("hours", "Operating Hours (Run Hours)"),
        ("kilometers", "Odometer Distance (km)"),
        ("miles", "Odometer Distance (mi)"),
        ("production_cycles", "Machine Cycles / Impressions"),
        ("none_calendar_only", "None (Calendar Time Only)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Pending Activation)"),
        ("active", "Active (Under Warranty)"),
        ("expiring_soon", "Expiring Soon (< 60 Days)"),
        ("expired", "Expired"),
        ("voided", "Voided (Condition Breach)"),
        ("claimed", "Under Active Claim"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "expiring_soon": "badge-amber",
        "expired": "badge-muted",
        "voided": "badge-red",
        "claimed": "badge-info",
    }

    WARRANTY_TYPE_CSS = {
        "oem_standard": "badge-info",
        "oem_extended": "badge-green",
        "third_party_extended": "badge-amber",
        "dealer_certified": "badge-slate",
        "refurbished_component": "badge-muted",
    }

    COVERAGE_SCOPE_CSS = {
        "comprehensive": "badge-green",
        "parts_and_labor": "badge-info",
        "parts_only": "badge-amber",
        "powertrain_major_components": "badge-slate",
        "corrosion_structural": "badge-muted",
    }

    title = models.CharField(
        max_length=255,
        help_text="Warranty policy title or contract agreement name",
    )
    warranty_certificate_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manufacturer/vendor warranty contract or certificate registration ID",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranties",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranties",
        help_text="Operational plant equipment or machinery",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranties",
        help_text="Asset category taxonomy",
    )
    warrantor_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provided_asset_warranties",
        help_text="OEM, authorized dealer, or warranty provider party",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_warranties",
        help_text="Transaction currency",
    )
    warranty_type = models.CharField(
        max_length=32,
        choices=WARRANTY_TYPE_CHOICES,
        default="oem_standard",
    )
    coverage_scope = models.CharField(
        max_length=32,
        choices=COVERAGE_SCOPE_CHOICES,
        default="comprehensive",
    )
    start_date = models.DateField(
        help_text="Warranty coverage inception or commissioning date",
    )
    end_date = models.DateField(
        help_text="Calendar warranty expiration date",
    )
    meter_type = models.CharField(
        max_length=24,
        choices=METER_TYPE_CHOICES,
        default="none_calendar_only",
    )
    meter_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Meter threshold limit (e.g. 5,000 hours or 100,000 km)",
    )
    parts_coverage_percent = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Covered replacement parts percentage (0-100%)",
    )
    labor_coverage_percent = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Covered technical labor percentage (0-100%)",
    )
    travel_dispatch_covered = models.BooleanField(
        default=True,
        help_text="Whether technician travel and on-site dispatch fees are covered",
    )
    deductible_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Per-incident warranty deductible payable by tenant",
    )
    contract_purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Purchase cost paid for extended warranty or service protection",
    )
    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Warranty coverage terms, exclusions, preventive maintenance mandates, and limits",
    )
    contract_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_asset_warranties",
        help_text="Scanned manufacturer warranty certificate or legal agreement",
    )
    service_contract = models.ForeignKey(
        "assets.AssetServiceContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_warranties",
        help_text="Associated 11.5 maintenance service contract SLA if unified",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_asset_warranties",
    )

    class Meta:
        ordering = ["-end_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_awar_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "end_date"], name="idx_awar_ten_date"),
            models.Index(fields=["tenant", "status"], name="idx_awar_ten_stat"),
            models.Index(fields=["tenant", "warranty_type"], name="idx_awar_ten_type"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_awar_ten_fa"),
            models.Index(fields=["tenant", "coverage_scope"], name="idx_awar_ten_scope"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def warranty_type_css(self):
        return self.WARRANTY_TYPE_CSS.get(self.warranty_type, "badge-info")

    @property
    def coverage_scope_css(self):
        return self.COVERAGE_SCOPE_CSS.get(self.coverage_scope, "badge-green")

    @property
    def is_currently_valid(self):
        today = timezone.now().date()
        return self.status == "active" and self.start_date <= today <= self.end_date
