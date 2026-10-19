"""Sales 8.11 — Customer Health Score model."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

HEALTH_BAND_CHOICES = [
    ("green", "Healthy (75-100)"),
    ("yellow", "Needs Attention (50-74)"),
    ("red", "At Risk (0-49)"),
]

TREND_CHOICES = [
    ("improving", "Improving"),
    ("stable", "Stable"),
    ("declining", "Declining"),
]

RISK_LEVEL_CHOICES = [
    ("low", "Low Risk"),
    ("medium", "Medium Risk"),
    ("high", "High Risk"),
    ("critical", "Critical Risk"),
]


class CustomerHealthScore(TenantNumbered):
    NUMBER_PREFIX = "CHS"

    account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_customer_health_scores",
    )
    evaluation_date = models.DateField(default=timezone.localdate)
    overall_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Composite health score between 0 and 100",
    )
    health_band = models.CharField(
        max_length=15,
        choices=HEALTH_BAND_CHOICES,
        default="green",
    )
    previous_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    score_trend = models.CharField(
        max_length=15,
        choices=TREND_CHOICES,
        default="stable",
    )
    product_usage_score = models.PositiveSmallIntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    support_ticket_score = models.PositiveSmallIntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    nps_sentiment_score = models.PositiveSmallIntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    relationship_score = models.PositiveSmallIntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    renewal_risk_score = models.PositiveSmallIntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    risk_level = models.CharField(
        max_length=15,
        choices=RISK_LEVEL_CHOICES,
        default="low",
    )
    risk_reasons = models.JSONField(
        default=list,
        blank=True,
        help_text="List of root risk factors e.g. ['low_adoption', 'unresolved_p1']",
    )
    active_alert_message = models.CharField(
        max_length=255,
        blank=True,
        help_text="Early warning alert text displayed on CSM cockpit",
    )
    is_churn_risk = models.BooleanField(
        default=False,
        help_text="Flag indicating critical retention intervention required",
    )
    license_utilization_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("80.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    open_support_tickets = models.PositiveIntegerField(default=0)
    latest_nps = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )
    last_activity_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-evaluation_date", "-overall_score"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_chs_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "evaluation_date"], name="sales_chs_acct_date_idx"),
            models.Index(fields=["tenant", "health_band"], name="sales_chs_band_idx"),
            models.Index(fields=["tenant", "is_churn_risk"], name="sales_chs_churn_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'CHS'} - {self.account.name} ({self.overall_score}/100)"

    def clean(self):
        super().clean()
        if self.account_id and self.tenant_id:
            if self.account.tenant_id != self.tenant_id:
                raise ValidationError({"account": "The selected customer account belongs to another workspace."})

        if self.overall_score is not None:
            if self.overall_score >= 75 and self.health_band == "red":
                raise ValidationError({"health_band": "Scores of 75 or higher cannot be assigned to the At Risk (Red) band."})
            if self.overall_score < 50 and self.health_band == "green":
                raise ValidationError({"health_band": "Scores below 50 cannot be assigned to the Healthy (Green) band."})

        if self.is_churn_risk and self.risk_level == "low":
            raise ValidationError({"risk_level": "Accounts flagged as active churn risk must have a Medium, High, or Critical risk level."})

    @property
    def health_badge_class(self):
        mapping = {
            "green": "badge-green",
            "yellow": "badge-amber",
            "red": "badge-red",
        }
        return mapping.get(self.health_band, "badge-slate")

    @property
    def risk_badge_class(self):
        mapping = {
            "low": "badge-green",
            "medium": "badge-amber",
            "high": "badge-red",
            "critical": "badge-red",
        }
        return mapping.get(self.risk_level, "badge-slate")

    @property
    def trend_icon(self):
        mapping = {
            "improving": "trending-up",
            "stable": "minus",
            "declining": "trending-down",
        }
        return mapping.get(self.score_trend, "minus")
