"""Sales 8.10 — `CommissionPlan` (`CMPL-`), incentive compensation plan design.

Supports flat revenue %, gross margin %, tiered quota attainment accelerators
(incremental vs retroactive brackets), SPIFs, recoverable and non-recoverable draws,
and clawback window terms.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

PLAN_TYPE_CHOICES = [
    ("flat_revenue", "Flat Revenue %"),
    ("gross_margin", "Gross Margin %"),
    ("tiered_quota", "Tiered Quota Attainment"),
    ("spif_only", "SPIF / Bonus Only"),
    ("hybrid", "Hybrid (Revenue + Tier + SPIF)"),
]

TIER_MODE_CHOICES = [
    ("incremental", "Incremental / Marginal Brackets"),
    ("retroactive", "Retroactive / All-In Payout"),
    ("not_applicable", "Not Applicable (Flat/No Tiers)"),
]

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("archived", "Archived"),
]

PAYOUT_FREQUENCY_CHOICES = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
]


class CommissionPlan(TenantNumbered):
    NUMBER_PREFIX = "CMPL"

    name = models.CharField(max_length=200, db_index=True)
    code = models.SlugField(max_length=60)
    description = models.TextField(blank=True)
    plan_type = models.CharField(
        max_length=30,
        choices=PLAN_TYPE_CHOICES,
        default="flat_revenue",
        db_index=True,
    )
    tier_mode = models.CharField(
        max_length=30,
        choices=TIER_MODE_CHOICES,
        default="not_applicable",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    payout_frequency = models.CharField(
        max_length=20,
        choices=PAYOUT_FREQUENCY_CHOICES,
        default="monthly",
    )
    effective_start = models.DateField(db_index=True)
    effective_end = models.DateField(null=True, blank=True)
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="sales_commission_plans",
    )
    target_region = models.CharField(max_length=100, blank=True)
    base_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Base commission rate percentage (0.00 to 100.00)",
    )
    tiers_config = models.JSONField(
        default=list,
        blank=True,
        help_text="List of bracket dicts: [{'min_pct': 0, 'max_pct': 100, 'rate_pct': 5.0}, ...]",
    )
    spif_config = models.JSONField(
        default=list,
        blank=True,
        help_text="List of SPIF dicts: [{'name': 'Q4 Booster', 'bonus_amount': 500.0, 'criteria': 'new_logo'}, ...]",
    )
    draw_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text="Guaranteed draw advance amount per settlement cycle",
    )
    is_draw_recoverable = models.BooleanField(
        default=True,
        help_text="True if advance is recoverable from future commission earnings",
    )
    clawback_window_days = models.PositiveIntegerField(
        default=90,
        help_text="Days post-deal-close during which cancellations trigger clawbacks",
    )
    tax_withholding_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Estimated local tax withholding rate percentage",
    )
    sales_quota = models.ForeignKey(
        "crm.SalesQuota",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_plans",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_commission_plans",
    )

    class Meta:
        ordering = ["-effective_start", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cmpl_tenant_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="sales_cmpl_tenant_code_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "effective_start"],
                name="sales_cmpl_stat_start_idx",
            ),
            models.Index(
                fields=["tenant", "plan_type"],
                name="sales_cmpl_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_plan_type_display()})"

    def clean(self):
        super().clean()

        # G1: Effective end date cannot be earlier than effective start date
        if self.effective_end and self.effective_start:
            if self.effective_end < self.effective_start:
                raise ValidationError(
                    {"effective_end": "Effective end date cannot precede effective start date."}
                )

        # G2: Validate tiers_config structure if tiered or hybrid
        if self.plan_type in ("tiered_quota", "hybrid"):
            if self.tier_mode == "not_applicable":
                raise ValidationError(
                    {"tier_mode": "Tiered or hybrid plans require an incremental or retroactive tier mode."}
                )
            if not isinstance(self.tiers_config, list) or len(self.tiers_config) == 0:
                raise ValidationError(
                    {"tiers_config": "Tiered or hybrid plans require at least one tier bracket configuration."}
                )
            last_max = -1
            for idx, tier in enumerate(self.tiers_config):
                if not isinstance(tier, dict):
                    raise ValidationError(
                        {"tiers_config": f"Tier {idx + 1} must be a JSON dictionary."}
                    )
                min_p = tier.get("min_pct")
                max_p = tier.get("max_pct")
                rate_p = tier.get("rate_pct")
                if min_p is None or max_p is None or rate_p is None:
                    raise ValidationError(
                        {"tiers_config": f"Tier {idx + 1} must contain 'min_pct', 'max_pct', and 'rate_pct'."}
                    )
                try:
                    min_p = float(min_p)
                    max_p = float(max_p)
                    rate_p = float(rate_p)
                except (ValueError, TypeError):
                    raise ValidationError(
                        {"tiers_config": f"Tier {idx + 1} values must be numeric."}
                    )
                if min_p < 0 or max_p <= min_p or rate_p < 0:
                    raise ValidationError(
                        {"tiers_config": f"Tier {idx + 1} has invalid range: min_pct < max_pct and rates >= 0 required."}
                    )
                if min_p < last_max:
                    raise ValidationError(
                        {"tiers_config": f"Tier {idx + 1} overlaps with preceding tier."}
                    )
                last_max = max_p

        # G3: Sales quota tenant isolation
        if self.sales_quota_id and self.tenant_id:
            if self.sales_quota.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"sales_quota": "Assigned sales quota belongs to another workspace."}
                )

        # G4: Owner tenant isolation
        if self.owner_id and self.tenant_id:
            if getattr(self.owner, "tenant_id", None) != self.tenant_id:
                raise ValidationError(
                    {"owner": "Plan owner must belong to the same workspace."}
                )
