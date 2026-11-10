from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetInsurancePolicy(TenantNumbered):
    """
    Asset and commercial equipment insurance policy [AINS-].
    Captures commercial property, machinery breakdown, boiler/pressure vessel,
    inland marine, and fleet policies, underwriter carriers and intermediary brokers,
    Statement of Values (SOV), deductible retentions, and annualized premium schedules.
    """

    NUMBER_PREFIX = "AINS"

    POLICY_TYPE_CHOICES = [
        ("commercial_property", "Commercial Property & Real Estate"),
        ("machinery_breakdown", "Machinery Breakdown & Mechanical Extrusion"),
        ("boiler_pressure_vessel", "Boiler, Pressure Vessel & Critical Plant"),
        ("inland_marine_transit", "Inland Marine & Equipment in Transit"),
        ("business_interruption", "Business Interruption & Loss of Profits"),
        ("commercial_auto_fleet", "Commercial Motor Vehicle & Heavy Mobile Fleet"),
        ("comprehensive_all_risk", "Comprehensive Industrial All-Risk (CAR/EAR)"),
    ]

    VALUATION_BASIS_CHOICES = [
        ("replacement_cost_value", "Replacement Cost Value (RCV - As New)"),
        ("actual_cash_value", "Actual Cash Value (ACV - Depreciated)"),
        ("agreed_stated_value", "Agreed Stated Value (Appraised)"),
        ("functional_replacement", "Functional Replacement Cost"),
    ]

    PREMIUM_FREQUENCY_CHOICES = [
        ("annual", "Annual Lump Sum"),
        ("semi_annual", "Semi-Annual (Bi-annual)"),
        ("quarterly", "Quarterly Installments"),
        ("monthly", "Monthly Direct Debit"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Quotation / Binding)"),
        ("active", "Active (In Force)"),
        ("pending_renewal", "Pending Renewal (< 45 Days)"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled / Surrendered"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "pending_renewal": "badge-amber",
        "expired": "badge-muted",
        "cancelled": "badge-red",
    }

    POLICY_TYPE_CSS = {
        "commercial_property": "badge-info",
        "machinery_breakdown": "badge-amber",
        "boiler_pressure_vessel": "badge-red",
        "inland_marine_transit": "badge-slate",
        "business_interruption": "badge-purple",
        "commercial_auto_fleet": "badge-info",
        "comprehensive_all_risk": "badge-green",
    }

    VALUATION_BASIS_CSS = {
        "replacement_cost_value": "badge-green",
        "actual_cash_value": "badge-amber",
        "agreed_stated_value": "badge-info",
        "functional_replacement": "badge-slate",
    }

    policy_number = models.CharField(
        max_length=100,
        help_text="Underwriter issued policy binder or certificate number",
    )
    title = models.CharField(
        max_length=255,
        help_text="Policy headline (e.g. FY26 Plant Machinery & Boiler Schedule)",
    )
    policy_type = models.CharField(
        max_length=32,
        choices=POLICY_TYPE_CHOICES,
        default="machinery_breakdown",
    )
    valuation_basis = models.CharField(
        max_length=28,
        choices=VALUATION_BASIS_CHOICES,
        default="replacement_cost_value",
    )
    underwriter_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="underwritten_asset_policies",
        help_text="Lead insurance underwriting carrier",
    )
    broker_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brokered_asset_policies",
        help_text="Insurance brokerage intermediary firm",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insurance_policies",
        help_text="Specific financial Fixed Asset (blank if blanket/fleet policy)",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insurance_policies",
        help_text="Specific operational machinery (blank if schedule-wide)",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="insurance_policies",
        help_text="Target category for category-wide coverage",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_insurance_policies",
        help_text="Policy valuation and premium currency",
    )
    effective_date = models.DateField(
        help_text="Policy inception / coverage start date",
    )
    expiration_date = models.DateField(
        help_text="Policy renewal / expiration cutoff date",
    )
    total_insured_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Statement of Values (SOV) / Sum insured limit",
    )
    deductible_retention = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Self-insured retention or per-claim deductible",
    )
    coinsurance_percentage = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Required coinsurance clause percentage (e.g. 80%, 90%, 100%)",
    )
    annual_premium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total annualized premium fee",
    )
    premium_frequency = models.CharField(
        max_length=16,
        choices=PREMIUM_FREQUENCY_CHOICES,
        default="annual",
    )
    coverage_terms = models.TextField(
        blank=True,
        help_text="Endorsements, named perils, territorial limits, and exclusion schedules",
    )
    policy_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_insurance_policies",
        help_text="Uploaded policy wording, endorsement schedule, or binder PDF",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    risk_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_asset_insurance_policies",
    )

    class Meta:
        ordering = ["-expiration_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_ains_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_ains_ten_stat"),
            models.Index(fields=["tenant", "expiration_date"], name="idx_ains_ten_exp"),
            models.Index(fields=["tenant", "policy_type"], name="idx_ains_ten_type"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_ains_ten_fa"),
            models.Index(fields=["tenant", "valuation_basis"], name="idx_ains_ten_val"),
        ]

    def __str__(self):
        return f"{self.number} ({self.policy_number}) - {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def policy_type_css(self):
        return self.POLICY_TYPE_CSS.get(self.policy_type, "badge-info")

    @property
    def valuation_basis_css(self):
        return self.VALUATION_BASIS_CSS.get(self.valuation_basis, "badge-green")

    @property
    def is_currently_in_force(self):
        today = timezone.now().date()
        return self.status == "active" and self.effective_date <= today <= self.expiration_date
