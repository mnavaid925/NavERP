from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetRiskRegister(TenantNumbered):
    """
    Asset Risk Register [ARK-].
    Centralized operational, financial, safety, regulatory, and reputational risk identification,
    evaluation (5x5 matrix & FMEA), residual scoring, and risk treatment strategy.
    Aligned with ISO 31000 and ISO 55000 standards.
    """

    NUMBER_PREFIX = "ARK"

    RISK_CATEGORY_CHOICES = [
        ("operational", "Operational & Reliability Risk"),
        ("financial", "Financial & Capital Asset Loss"),
        ("safety_health", "Occupational Safety & Health (EHS)"),
        ("environmental", "Environmental Release / Contamination"),
        ("cybersecurity", "OT / IoT / SCADA Cybersecurity"),
        ("regulatory", "Regulatory & Statutory Non-Compliance"),
        ("geopolitical_supply_chain", "Geopolitical & Supply Chain Disruption"),
        ("reputational", "Reputational & Brand Damage"),
    ]

    THREAT_SOURCE_CHOICES = [
        ("equipment_wear", "Mechanical / Component Wear & Aging"),
        ("operator_error", "Human / Operator Procedure Error"),
        ("cyber_attack", "Cyber Attack / Ransomware / Malware"),
        ("extreme_weather", "Extreme Weather / Natural Disaster"),
        ("supply_chain_disruption", "Supply Chain / Sole-Source Disruption"),
        ("vendor_insolvency", "Vendor Bankruptcy / Contract Default"),
        ("regulatory_mandate", "Statutory / Regulatory Rule Change"),
        ("utility_grid_failure", "Utility / Power Grid Outage"),
    ]

    TREATMENT_STRATEGY_CHOICES = [
        ("mitigate", "Mitigate (Engineering Controls & PM)"),
        ("transfer", "Transfer (Insurance / Contractual)"),
        ("avoid", "Avoid (Decommission / Process Change)"),
        ("accept", "Accept (Documented Residual Risk)"),
    ]

    STATUS_CHOICES = [
        ("identified", "Risk Identified"),
        ("assessed", "Risk Assessed & Scored"),
        ("treating", "Active Treatment / Remediation"),
        ("monitored", "Monitored / Stable"),
        ("closed", "Risk Retired / Closed"),
    ]

    RISK_LEVEL_CHOICES = [
        ("low", "Low Risk (1-4)"),
        ("medium", "Medium Risk (5-9)"),
        ("high", "High Risk (10-14)"),
        ("critical", "Critical Risk (15-25)"),
    ]

    REVIEW_FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annually", "Semi-Annually"),
        ("annually", "Annually"),
    ]

    STATUS_CSS = {
        "identified": "badge-slate",
        "assessed": "badge-info",
        "treating": "badge-amber",
        "monitored": "badge-purple",
        "closed": "badge-green",
    }

    RISK_LEVEL_CSS = {
        "low": "badge-green",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    RISK_CATEGORY_CSS = {
        "operational": "badge-info",
        "financial": "badge-purple",
        "safety_health": "badge-red",
        "environmental": "badge-green",
        "cybersecurity": "badge-amber",
        "regulatory": "badge-slate",
        "geopolitical_supply_chain": "badge-amber",
        "reputational": "badge-muted",
    }

    TREATMENT_STRATEGY_CSS = {
        "mitigate": "badge-info",
        "transfer": "badge-purple",
        "avoid": "badge-amber",
        "accept": "badge-slate",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="asset_risks",
    )
    title = models.CharField(
        max_length=255,
        help_text="Descriptive title of operational or infrastructure risk",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_risks",
        help_text="Specific physical plant equipment or facility asset",
    )
    category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_risks",
        help_text="Asset taxonomy category for fleet-wide risk profiles",
    )
    risk_category = models.CharField(
        max_length=30,
        choices=RISK_CATEGORY_CHOICES,
        default="operational",
    )
    threat_source = models.CharField(
        max_length=30,
        choices=THREAT_SOURCE_CHOICES,
        default="equipment_wear",
    )
    failure_mode = models.CharField(
        max_length=255,
        blank=True,
        help_text="FMEA failure mode, trigger condition, or failure scenario",
    )
    description = models.TextField(
        blank=True,
        help_text="Comprehensive technical description and operational consequence",
    )
    inherent_likelihood = models.PositiveSmallIntegerField(
        default=3,
        help_text="Inherent Likelihood (1=Rare to 5=Almost Certain)",
    )
    inherent_impact = models.PositiveSmallIntegerField(
        default=3,
        help_text="Inherent Impact (1=Insignificant to 5=Catastrophic)",
    )
    inherent_risk_score = models.PositiveIntegerField(
        default=9,
        editable=False,
        help_text="Inherent Risk Score (Likelihood x Impact, 1-25)",
    )
    inherent_risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default="medium",
        editable=False,
    )
    residual_likelihood = models.PositiveSmallIntegerField(
        default=2,
        help_text="Residual Likelihood post-mitigation (1-5)",
    )
    residual_impact = models.PositiveSmallIntegerField(
        default=2,
        help_text="Residual Impact post-mitigation (1-5)",
    )
    residual_risk_score = models.PositiveIntegerField(
        default=4,
        editable=False,
        help_text="Residual Risk Score (Likelihood x Impact, 1-25)",
    )
    residual_risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default="low",
        editable=False,
    )
    risk_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_asset_risks",
        help_text="Assigned risk manager or engineer",
    )
    treatment_strategy = models.CharField(
        max_length=20,
        choices=TREATMENT_STRATEGY_CHOICES,
        default="mitigate",
    )
    financial_exposure_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated financial loss or replacement impact",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="identified",
    )
    review_frequency = models.CharField(
        max_length=20,
        choices=REVIEW_FREQUENCY_CHOICES,
        default="quarterly",
    )
    next_review_date = models.DateField(
        null=True,
        blank=True,
        help_text="Next scheduled risk reassessment date",
    )
    last_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_ark_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_ark_ten_stat"),
            models.Index(fields=["tenant", "risk_category"], name="idx_ark_ten_cat"),
            models.Index(fields=["tenant", "inherent_risk_level"], name="idx_ark_ten_in_lvl"),
            models.Index(fields=["tenant", "residual_risk_level"], name="idx_ark_ten_res_lvl"),
            models.Index(fields=["tenant", "asset"], name="idx_ark_ten_ast"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_inherent_risk_level_display()})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def inherent_risk_level_badge_class(self):
        return self.RISK_LEVEL_CSS.get(self.inherent_risk_level, "badge-slate")

    @property
    def residual_risk_level_badge_class(self):
        return self.RISK_LEVEL_CSS.get(self.residual_risk_level, "badge-slate")

    @property
    def risk_category_badge_class(self):
        return self.RISK_CATEGORY_CSS.get(self.risk_category, "badge-slate")

    @property
    def treatment_strategy_badge_class(self):
        return self.TREATMENT_STRATEGY_CSS.get(self.treatment_strategy, "badge-slate")

    @staticmethod
    def _score_to_level(score: int) -> str:
        if score <= 4:
            return "low"
        if score <= 9:
            return "medium"
        if score <= 14:
            return "high"
        return "critical"

    def calculate_scores(self):
        # Bound likelihood and impact between 1 and 5
        inh_l = max(1, min(5, self.inherent_likelihood or 1))
        inh_i = max(1, min(5, self.inherent_impact or 1))
        self.inherent_likelihood = inh_l
        self.inherent_impact = inh_i
        self.inherent_risk_score = inh_l * inh_i
        self.inherent_risk_level = self._score_to_level(self.inherent_risk_score)

        res_l = max(1, min(5, self.residual_likelihood or 1))
        res_i = max(1, min(5, self.residual_impact or 1))
        self.residual_likelihood = res_l
        self.residual_impact = res_i
        self.residual_risk_score = res_l * res_i
        self.residual_risk_level = self._score_to_level(self.residual_risk_score)

    def save(self, *args, **kwargs):
        self.calculate_scores()
        super().save(*args, **kwargs)
