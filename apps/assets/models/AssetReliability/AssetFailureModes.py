from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetFailureMode(TenantNumbered):
    """
    SAE JA1012 / ISO 14224 Failure Mode & Effects Analysis (FMEA / FMECA) and
    Reliability-Centered Maintenance (RCM) register [AFMA-].
    Computes Risk Priority Number (RPN = Severity × Occurrence × Detection, 1–1000),
    evaluates risk tiers, and links proactive mitigation tasks to maintenance schedules.
    """

    NUMBER_PREFIX = "AFMA"

    RISK_LEVEL_CHOICES = [
        ("low", "Low Risk (RPN < 100)"),
        ("medium", "Medium Risk (RPN 100 - 250)"),
        ("high", "High Risk (RPN 251 - 500)"),
        ("extreme", "Extreme Risk (RPN > 500)"),
    ]

    RCM_STRATEGY_CHOICES = [
        ("condition_based", "Condition-Based Maintenance (CBM / PdM)"),
        ("time_based_pm", "Time-Based Preventive Maintenance (PM)"),
        ("meter_based_pm", "Meter / Run-Hours Based PM"),
        ("failure_finding", "Failure-Finding Task (Hidden Failure Inspection)"),
        ("run_to_failure", "Run-to-Failure (Corrective Only)"),
        ("redesign_required", "Engineering Redesign / Modification Required"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Under Study)"),
        ("active", "Active (Mitigation Enforced)"),
        ("superseded", "Superseded (Obsolete)"),
        ("archived", "Archived"),
    ]

    RISK_LEVEL_CSS = {
        "low": "badge-green",
        "medium": "badge-info",
        "high": "badge-amber",
        "extreme": "badge-red",
    }

    RCM_STRATEGY_CSS = {
        "condition_based": "badge-info",
        "time_based_pm": "badge-slate",
        "meter_based_pm": "badge-slate",
        "failure_finding": "badge-amber",
        "run_to_failure": "badge-muted",
        "redesign_required": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "superseded": "badge-amber",
        "archived": "badge-muted",
    }

    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failure_modes",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failure_modes",
        help_text="Operational equipment record",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failure_modes",
        help_text="Asset category taxonomy",
    )
    component_subsystem = models.CharField(
        max_length=200,
        help_text="Component, assembly, or subsystem (e.g. Impeller, Bearing, Hydraulic Seal)",
    )
    function_description = models.TextField(
        help_text="Primary engineering function of the component in service",
    )
    functional_failure = models.CharField(
        max_length=255,
        help_text="Description of functional failure (inability to meet performance standard)",
    )
    failure_mode = models.CharField(
        max_length=255,
        help_text="Physical mechanism of failure (e.g. Fatigue Spalling, Cavitation Erosion, Seal Degradation)",
    )
    failure_cause = models.TextField(
        help_text="Root or proximate cause leading to the failure mode",
    )
    failure_effect = models.TextField(
        help_text="Local and plant-wide consequences on operations, safety, and environment",
    )
    severity_score = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Failure Severity ranking (1=Negligible to 10=Catastrophic/Hazardous)",
    )
    occurrence_score = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Failure Frequency / Occurrence ranking (1=Extremely Unlikely to 10=Frequent)",
    )
    detection_score = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Failure Detection ranking (1=Almost Certain to 10=Undetectable prior to failure)",
    )
    rpn = models.PositiveIntegerField(
        default=125,
        editable=False,
        help_text="Risk Priority Number: Severity × Occurrence × Detection (1 - 1000)",
    )
    risk_level = models.CharField(
        max_length=16,
        choices=RISK_LEVEL_CHOICES,
        default="medium",
        editable=False,
    )
    rcm_strategy = models.CharField(
        max_length=32,
        choices=RCM_STRATEGY_CHOICES,
        default="condition_based",
    )
    strategy_rationale = models.TextField(
        blank=True,
        help_text="Engineering justification for selected maintenance policy",
    )
    mitigation_task = models.TextField(
        blank=True,
        help_text="Specific proactive task description or inspection SOP",
    )
    linked_maintenance_schedule = models.ForeignKey(
        "assets.AssetMaintenanceSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failure_modes",
        help_text="Preventive maintenance schedule enforcing this mitigation",
    )
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessed_asset_failure_modes",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    class Meta:
        ordering = ["-rpn", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_afma_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "rpn"], name="idx_afma_ten_rpn"),
            models.Index(fields=["tenant", "risk_level"], name="idx_afma_ten_risk"),
            models.Index(fields=["tenant", "rcm_strategy"], name="idx_afma_ten_strat"),
            models.Index(fields=["tenant", "status"], name="idx_afma_ten_stat"),
        ]

    def __str__(self):
        return f"{self.number} - {self.component_subsystem}: {self.failure_mode} (RPN {self.rpn})"

    def calculate_rpn(self):
        s = self.severity_score or 1
        o = self.occurrence_score or 1
        d = self.detection_score or 1
        self.rpn = s * o * d
        if self.rpn > 500:
            self.risk_level = "extreme"
        elif self.rpn >= 251:
            self.risk_level = "high"
        elif self.rpn >= 100:
            self.risk_level = "medium"
        else:
            self.risk_level = "low"

    def calculate_rpn_and_risk_level(self):
        return self.calculate_rpn()

    def save(self, *args, **kwargs):
        self.calculate_rpn()
        return super().save(*args, **kwargs)

    @property
    def risk_level_css(self):
        return self.RISK_LEVEL_CSS.get(self.risk_level, "badge-slate")

    @property
    def rcm_strategy_css(self):
        return self.RCM_STRATEGY_CSS.get(self.rcm_strategy, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
