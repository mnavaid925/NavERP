from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetAnalytics._validators import (
    ZERO,
    add_field_error,
    cap_decimal,
    q2,
    validate_tenant_fks,
)


def _default_replacement_year():
    return timezone.localdate().year + 1


class AssetReplacementPlan(TenantNumbered):
    """
    Asset Replacement Plan & CapEx Forecast [ARPL-].
    Tracks end-of-life forecasting, Facility Condition Index (FCI), risk-weighted priority scoring,
    inflation-adjusted replacement CapEx, deferral penalty, and optional AREQ requisition linkage.
    """

    NUMBER_PREFIX = "ARPL"

    QUARTER_CHOICES = [
        ("q1", "Q1 (Jan-Mar)"),
        ("q2", "Q2 (Apr-Jun)"),
        ("q3", "Q3 (Jul-Sep)"),
        ("q4", "Q4 (Oct-Dec)"),
    ]

    STRATEGY_CHOICES = [
        ("like_for_like", "Like-for-Like Replacement"),
        ("technology_upgrade", "Technology / Efficiency Upgrade"),
        ("capacity_expansion", "Capacity Expansion"),
        ("consolidate_retire", "Consolidate & Retire"),
        ("refurbish_extend", "Major Overhaul / Life Extension"),
    ]

    FUNDING_STATUS_CHOICES = [
        ("unfunded", "Unfunded Backlog"),
        ("requested", "CapEx Requested"),
        ("budget_allocated", "Budget Allocated"),
        ("deferred", "Deferred"),
    ]

    STATUS_CHOICES = [
        ("forecasted", "Forecasted"),
        ("proposed", "Proposed for CIP"),
        ("approved", "Approved"),
        ("scheduled", "Scheduled"),
        ("executed", "Executed"),
        ("deferred", "Deferred"),
        ("cancelled", "Cancelled"),
    ]

    PRIORITY_BAND_CHOICES = [
        ("critical", "Critical Priority"),
        ("high", "High Priority"),
        ("medium", "Medium Priority"),
        ("low", "Low Priority"),
    ]

    STATUS_CSS = {
        "forecasted": "badge-slate",
        "proposed": "badge-info",
        "approved": "badge-green",
        "scheduled": "badge-info",
        "executed": "badge-green",
        "deferred": "badge-amber",
        "cancelled": "badge-muted",
    }

    LOCKED_STATUSES = {"approved", "scheduled", "executed", "cancelled"}

    ALLOWED_TRANSITIONS = {
        "forecasted": {"proposed", "approved", "deferred", "cancelled"},
        "proposed": {"approved", "deferred", "cancelled"},
        "approved": {"scheduled", "deferred", "cancelled"},
        "scheduled": {"executed", "deferred", "cancelled"},
        "deferred": {"proposed", "cancelled"},
        "executed": set(),
        "cancelled": set(),
    }

    FUNDING_STATUS_CSS = {
        "unfunded": "badge-red",
        "requested": "badge-amber",
        "budget_allocated": "badge-green",
        "deferred": "badge-slate",
    }

    PRIORITY_BAND_CSS = {
        "critical": "badge-red",
        "high": "badge-amber",
        "medium": "badge-info",
        "low": "badge-green",
    }

    title = models.CharField(
        max_length=255,
        help_text="Replacement project title or capital asset initiative",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_replacement_plans",
    )
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_replacement_plans",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_replacement_plans",
    )
    condition_assessment = models.ForeignKey(
        "assets.AssetConditionAssessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    lifecycle_analysis = models.ForeignKey(
        "assets.AssetLifecycleCostAnalysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    capital_budget = models.ForeignKey(
        "accounting.Budget",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_replacement_plans",
    )
    linked_requisition = models.ForeignKey(
        "assets.AssetRequisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replacement_plans",
    )
    planner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_asset_replacements",
    )

    predicted_eol_date = models.DateField(null=True, blank=True)
    remaining_useful_life_months = models.PositiveIntegerField(default=12)
    planned_replacement_year = models.PositiveIntegerField(default=_default_replacement_year)
    planned_quarter = models.CharField(
        max_length=5,
        choices=QUARTER_CHOICES,
        default="q1",
    )
    replacement_strategy = models.CharField(
        max_length=25,
        choices=STRATEGY_CHOICES,
        default="like_for_like",
    )
    funding_status = models.CharField(
        max_length=24,
        choices=FUNDING_STATUS_CHOICES,
        default="unfunded",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="forecasted",
    )

    # Risk-Weighted Priority Scoring
    condition_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("50.00"),
        help_text="Asset health score (0=Failed, 100=Like-New)",
    )
    criticality_weight = models.PositiveSmallIntegerField(
        default=5,
        help_text="Operational criticality scale from 1 (Low) to 10 (Mission-Critical)",
    )
    failure_risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("50.00"),
        help_text="Estimated failure risk index from 0 to 100",
    )
    priority_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    priority_band = models.CharField(
        max_length=15,
        choices=PRIORITY_BAND_CHOICES,
        default="medium",
    )

    # Capital Financial Forecast
    current_replacement_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    deferred_maintenance_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fci_ratio_pct = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estimated_replacement_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    inflation_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("4.00"),
    )
    inflation_adjusted_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estimated_salvage_recovery = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    deferral_penalty_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Annualized excess maintenance & downtime penalty if replacement is deferred 1 year",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-priority_score", "planned_replacement_year", "-id"]
        verbose_name = "Asset Replacement Plan"
        verbose_name_plural = "Asset Replacement Plans"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_arpl_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_arpl_ten_stat"),
            models.Index(fields=["tenant", "funding_status"], name="idx_arpl_ten_fund"),
            models.Index(fields=["tenant", "priority_band"], name="idx_arpl_ten_prio"),
            models.Index(fields=["tenant", "planned_replacement_year"], name="idx_arpl_ten_year"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def funding_status_badge_class(self):
        return self.FUNDING_STATUS_CSS.get(self.funding_status, "badge-slate")

    @property
    def priority_band_badge_class(self):
        return self.PRIORITY_BAND_CSS.get(self.priority_band, "badge-slate")

    @property
    def net_capital_requirement(self):
        return q2(max(ZERO, (self.inflation_adjusted_cost or ZERO) - (self.estimated_salvage_recovery or ZERO)))

    def recalculate_metrics(self):
        """Calculate Facility Condition Index (FCI), priority score/band, and inflation-adjusted CapEx."""
        if (
            self.tenant_id
            and self.condition_assessment_id
            and self.condition_assessment
            and self.condition_assessment.tenant_id == self.tenant_id
            and (self.condition_score is None or self.condition_score == Decimal("50.00"))
        ):
            self.condition_score = q2(self.condition_assessment.health_score)

        if (
            self.tenant_id
            and self.lifecycle_analysis_id
            and self.lifecycle_analysis
            and self.lifecycle_analysis.tenant_id == self.tenant_id
            and (self.current_replacement_value or ZERO) <= ZERO
            and (self.lifecycle_analysis.current_replacement_value or ZERO) > ZERO
        ):
            self.current_replacement_value = q2(self.lifecycle_analysis.current_replacement_value)

        crv = self.current_replacement_value or ZERO
        deferred = self.deferred_maintenance_cost or ZERO
        if crv > ZERO:
            self.fci_ratio_pct = cap_decimal((deferred / crv) * Decimal("100.00"))
        else:
            self.fci_ratio_pct = ZERO

        cond = min(max(self.condition_score if self.condition_score is not None else Decimal("50.00"), ZERO), Decimal("100.00"))
        fail_risk = min(max(self.failure_risk_score if self.failure_risk_score is not None else Decimal("50.00"), ZERO), Decimal("100.00"))
        crit = min(max(Decimal(int(self.criticality_weight or 5)), Decimal("1")), Decimal("10")) * Decimal("10.00")

        score = (Decimal("100.00") - cond) * Decimal("0.40") + fail_risk * Decimal("0.35") + crit * Decimal("0.25")
        self.priority_score = cap_decimal(score, max_abs=Decimal("9999.99"))

        if self.priority_score >= Decimal("75.00"):
            self.priority_band = "critical"
        elif self.priority_score >= Decimal("50.00"):
            self.priority_band = "high"
        elif self.priority_score >= Decimal("25.00"):
            self.priority_band = "medium"
        else:
            self.priority_band = "low"

        current_year = timezone.localdate().year
        target_year = int(self.planned_replacement_year or current_year)
        years_out = min(20, max(0, target_year - current_year))
        inf_rate = max(ZERO, min(Decimal("50.00"), self.inflation_rate_pct or ZERO)) / Decimal("100.00")
        base_cost = max(ZERO, self.estimated_replacement_cost or ZERO)
        self.inflation_adjusted_cost = cap_decimal(
            base_cost * ((Decimal("1.00") + inf_rate) ** years_out),
            max_abs=Decimal("999999999999.99"),
        )

    def clean(self):
        errors = {}
        validate_tenant_fks(
            self,
            errors,
            [
                "fixed_asset",
                "operational_asset",
                "asset_category",
                "asset_model",
                "org_unit",
                "location",
                "condition_assessment",
                "lifecycle_analysis",
                "capital_budget",
                "linked_requisition",
                "planner",
            ],
        )
        if not (1 <= (self.criticality_weight or 0) <= 10):
            add_field_error(errors, "criticality_weight", "Criticality weight must be between 1 and 10.")
        if self.remaining_useful_life_months is not None and not (0 <= int(self.remaining_useful_life_months) <= 1200):
            add_field_error(errors, "remaining_useful_life_months", "Remaining useful life must be between 0 and 1200 months.")
        if self.condition_score is not None and (self.condition_score < ZERO or self.condition_score > Decimal("100.00")):
            add_field_error(errors, "condition_score", "Condition score must be between 0 and 100.")
        if self.failure_risk_score is not None and (self.failure_risk_score < ZERO or self.failure_risk_score > Decimal("100.00")):
            add_field_error(errors, "failure_risk_score", "Failure risk score must be between 0 and 100.")
        if self.inflation_rate_pct is not None and (self.inflation_rate_pct < ZERO or self.inflation_rate_pct > Decimal("50.00")):
            add_field_error(errors, "inflation_rate_pct", "Inflation rate must be between 0% and 50%.")
        if self.planned_replacement_year is not None and not (2000 <= int(self.planned_replacement_year) <= 2100):
            add_field_error(errors, "planned_replacement_year", "Planned replacement year must be between 2000 and 2100.")
        for fname in (
            "current_replacement_value",
            "deferred_maintenance_cost",
            "estimated_replacement_cost",
            "estimated_salvage_recovery",
            "deferral_penalty_cost",
        ):
            val = getattr(self, fname, None)
            if val is not None and val < ZERO:
                add_field_error(errors, fname, "Monetary amount cannot be negative.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is None:
            self.recalculate_metrics()
        return super().save(*args, **kwargs)
