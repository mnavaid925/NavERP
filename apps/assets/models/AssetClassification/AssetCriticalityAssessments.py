from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetCriticalityAssessment(TenantNumbered):
    """Multi-factor risk assessment, failure consequence analysis, and ABC criticality rating [ACRT-]."""

    NUMBER_PREFIX = "ACRT"

    ABC_RATING_CHOICES = [
        ("A", "Class A - Critical / Mission-Essential"),
        ("B", "Class B - Important / Severe Impact"),
        ("C", "Class C - Standard / Low Impact"),
    ]

    STRATEGY_CHOICES = [
        ("rcm_predictive", "RCM / Predictive (PdM)"),
        ("rigorous_pm", "Rigorous Preventive (Time/Meter PM)"),
        ("standard_pm", "Standard Preventive Maintenance"),
        ("run_to_failure", "Run-to-Failure (Corrective)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Assessment"),
        ("reviewed", "Under Peer Review"),
        ("approved", "Approved & Active"),
        ("superseded", "Superseded by Newer Audit"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "reviewed": "badge-info",
        "approved": "badge-green",
        "superseded": "badge-muted",
    }

    ABC_CSS = {
        "A": "badge-red",
        "B": "badge-amber",
        "C": "badge-slate",
    }

    title = models.CharField(
        max_length=200,
        help_text="Assessment audit title, e.g. Annual Criticality Review - Chiller Plant #2",
    )
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="criticality_assessments",
        help_text="Operational physical asset evaluated in this risk review",
    )
    assessor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_assessments",
        help_text="Lead reliability engineer or inspector conducting review",
    )
    assessment_date = models.DateField(
        default=timezone.now,
        help_text="Date consequence analysis was performed",
    )

    safety_impact = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Personnel safety consequence score (1 = Negligible, 5 = Fatality / Critical Hazard)",
    )
    environmental_impact = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Environmental hazard score (1 = Zero release, 5 = Major reportable spill / emission)",
    )
    operational_downtime_impact = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Production throughput loss score (1 = No impact, 5 = Total plant bottleneck outage)",
    )
    financial_impact = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Repair and business interruption cost (1 = <$1k, 5 = >$250k catastrophic loss)",
    )
    regulatory_compliance_impact = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Legal/statutory compliance impact (1 = Minor internal, 5 = Revocation of operating permit)",
    )

    is_single_point_of_failure = models.BooleanField(
        default=False,
        help_text="True if no redundant standby unit exists (+5 risk penalty added to score)",
    )
    composite_score = models.PositiveSmallIntegerField(
        default=5,
        help_text="Auto-calculated consequence score sum plus redundancy penalty (Range: 5 to 30)",
    )
    abc_rating = models.CharField(
        max_length=1,
        choices=ABC_RATING_CHOICES,
        default="C",
        help_text="Derived operational criticality tier (A = Mission Critical, B = Severe, C = Standard)",
    )

    recommended_strategy = models.CharField(
        max_length=24,
        choices=STRATEGY_CHOICES,
        default="standard_pm",
        help_text="Recommended reliability-centered maintenance strategy based on score",
    )
    assessment_status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="draft",
    )
    review_cycle_months = models.PositiveIntegerField(
        default=12,
        help_text="Recommended re-assessment interval in months (e.g. Class A = 6 mos, Class C = 24 mos)",
    )
    next_assessment_due = models.DateField(
        null=True,
        blank=True,
        help_text="Scheduled date for subsequent criticality audit",
    )
    findings_and_mitigation = models.TextField(
        blank=True,
        help_text="Risk evaluation findings, failure mode observations, and recommended mitigation actions",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_assessments",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "assets_criticality_assessment"
        ordering = ["-assessment_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_acrt_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "asset"], name="idx_acrt_ten_asset"),
            models.Index(fields=["tenant", "assessment_status"], name="idx_acrt_ten_status"),
            models.Index(fields=["tenant", "abc_rating"], name="idx_acrt_ten_abc"),
            models.Index(fields=["tenant", "assessment_date"], name="idx_acrt_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_abc_rating_display()})"

    def calculate_composite_score(self):
        """Derives composite risk score and ABC classification tier."""
        base_sum = (
            (self.safety_impact or 1)
            + (self.environmental_impact or 1)
            + (self.operational_downtime_impact or 1)
            + (self.financial_impact or 1)
            + (self.regulatory_compliance_impact or 1)
        )
        if self.is_single_point_of_failure:
            base_sum += 5

        self.composite_score = base_sum

        # Derive ABC rating
        if base_sum >= 20 or (self.is_single_point_of_failure and (self.safety_impact >= 4 or self.operational_downtime_impact >= 4)):
            self.abc_rating = "A"
            if not self.recommended_strategy or self.recommended_strategy == "standard_pm":
                self.recommended_strategy = "rcm_predictive"
        elif base_sum >= 12:
            self.abc_rating = "B"
            if not self.recommended_strategy or self.recommended_strategy == "standard_pm":
                self.recommended_strategy = "rigorous_pm"
        else:
            self.abc_rating = "C"

    def save(self, *args, **kwargs):
        self.calculate_composite_score()
        super().save(*args, **kwargs)

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.assessment_status, "badge-slate")

    @property
    def abc_css(self):
        return self.ABC_CSS.get(self.abc_rating, "badge-slate")
