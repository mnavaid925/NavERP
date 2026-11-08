from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetCapitalization(TenantNumbered):
    """Cost basis determination, CIP clearance, and financial FixedAsset capitalization [ACAP-]."""

    NUMBER_PREFIX = "ACAP"

    DEPRECIATION_METHOD_CHOICES = [
        ("straight_line", "Straight Line"),
        ("declining_balance", "Declining Balance (200%)"),
        ("units_of_production", "Units of Production"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Evaluation"),
        ("approved", "Approved for Capitalization"),
        ("capitalized", "Capitalized into Fixed Assets"),
        ("reversed", "Reversed"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "approved": "badge-amber",
        "capitalized": "badge-green",
        "reversed": "badge-red",
    }

    # Core identity
    title = models.CharField(max_length=200, help_text="Capitalization event title")
    asset_name = models.CharField(max_length=255, help_text="Formal asset designation for the fixed asset register")

    # Upstream sourcing links
    acquisition_receipt = models.ForeignKey(
        "assets.AssetAcquisitionReceipt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capitalization_events",
        help_text="Dock receipt certifying physical arrival and inspection",
    )
    requisition = models.ForeignKey(
        "assets.AssetRequisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capitalization_events",
        help_text="Original capital expenditure requisition",
    )

    # Cost basis buildup
    purchase_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Base invoice purchase cost")
    freight_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Ocean, air, or ground freight shipping charges")
    installation_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Rigging, electrical installation, and calibration fees")
    customs_duties_cost = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Import tariffs, border taxes, and customs brokerage")
    other_initial_costs = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Ancillary pre-operation commissioning expenditures")
    total_cost_basis = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Total capitalized cost basis (GAAP / IFRS)")

    # CIP & GL Account clearing
    is_cip_conversion = models.BooleanField(default=False, help_text="Whether this capitalizes an existing Construction-in-Progress asset")
    cip_gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_cip_clearances",
        help_text="CIP balance sheet clearing account",
    )
    asset_gl_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_capitalizations",
        help_text="Target balance sheet Fixed Asset cost account",
    )

    # Financial depreciation parameters
    depreciation_method = models.CharField(max_length=30, choices=DEPRECIATION_METHOD_CHOICES, default="straight_line")
    useful_life_months = models.PositiveIntegerField(default=60, help_text="Useful life in months for depreciation schedules")
    salvage_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), help_text="Estimated residual / scrap value at end of life")
    in_service_date = models.DateField(default=timezone.now, help_text="Date placed in service; depreciation begins on this date")

    # Downstream asset master linkages
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capitalization_records",
        help_text="Linked financial fixed asset in Module 2 accounting ledger",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capitalization_records",
        help_text="Linked operational physical asset in SCM/plant register",
    )

    # Status & execution tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    capitalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capitalized_assets",
    )
    capitalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "assets_capitalization"
        ordering = ["-in_service_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_acap_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_acap_ten_stat"),
            models.Index(fields=["tenant", "depreciation_method"], name="idx_acap_ten_meth"),
            models.Index(fields=["tenant", "in_service_date"], name="idx_acap_ten_insvc"),
            models.Index(fields=["tenant", "created_at"], name="idx_acap_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.asset_name}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def calculate_total_cost_basis(self):
        return (
            (self.purchase_cost or Decimal("0.00"))
            + (self.freight_cost or Decimal("0.00"))
            + (self.installation_cost or Decimal("0.00"))
            + (self.customs_duties_cost or Decimal("0.00"))
            + (self.other_initial_costs or Decimal("0.00"))
        )

    def save(self, *args, **kwargs):
        self.total_cost_basis = self.calculate_total_cost_basis()
        super().save(*args, **kwargs)

    def can_execute_capitalization(self):
        return self.status in ("draft", "approved")

    def can_reverse(self):
        return self.status == "capitalized"

    def can_reverse_capitalization(self):
        return self.can_reverse()
