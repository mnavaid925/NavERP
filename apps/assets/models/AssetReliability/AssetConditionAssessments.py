from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetConditionAssessment(TenantNumbered):
    """
    Asset physical condition assessment and non-destructive testing (NDT) diagnostic record [ACAS-].
    Captures visual inspections, ultrasonic thickness, thermography, vibration pen screenings,
    oil analysis, condition grade (1-5), and health index scoring (0-100).
    """

    NUMBER_PREFIX = "ACAS"

    ASSESSMENT_TYPE_CHOICES = [
        ("visual_inspection", "Visual Inspection"),
        ("ndt_ultrasonic", "NDT - Ultrasonic Thickness"),
        ("ndt_thermography", "NDT - Infrared Thermography"),
        ("ndt_vibration_pen", "NDT - Vibration Screening Pen"),
        ("ndt_dye_penetrant", "NDT - Dye Penetrant Testing"),
        ("ndt_magnetic_particle", "NDT - Magnetic Particle Inspection"),
        ("oil_analysis", "Lube Oil & Fluid Lab Analysis"),
        ("diagnostic_checklist", "Comprehensive Diagnostic Checklist"),
    ]

    CONDITION_GRADE_CHOICES = [
        ("grade_1_excellent", "Grade 1 - Excellent (As New)"),
        ("grade_2_good", "Grade 2 - Good (Minor Wear)"),
        ("grade_3_fair", "Grade 3 - Fair (Noticeable Wear)"),
        ("grade_4_poor", "Grade 4 - Poor (Impaired Function)"),
        ("grade_5_critical", "Grade 5 - Critical (Severe Failure Hazard)"),
    ]

    OPERATING_STATUS_CHOICES = [
        ("normal_operation", "Normal Operation"),
        ("operational_with_defects", "Operational with Minor Defects"),
        ("reduced_capacity", "Derated / Reduced Capacity"),
        ("quarantined_unsafe", "Quarantined / Unsafe to Operate"),
        ("decommission_recommended", "Decommissioning Recommended"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (In Progress)"),
        ("completed", "Completed"),
        ("reviewed", "Reviewed & Approved"),
        ("archived", "Archived"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "completed": "badge-info",
        "reviewed": "badge-green",
        "archived": "badge-muted",
    }

    CONDITION_GRADE_CSS = {
        "grade_1_excellent": "badge-green",
        "grade_2_good": "badge-info",
        "grade_3_fair": "badge-amber",
        "grade_4_poor": "badge-red",
        "grade_5_critical": "badge-red",
    }

    OPERATING_STATUS_CSS = {
        "normal_operation": "badge-green",
        "operational_with_defects": "badge-amber",
        "reduced_capacity": "badge-amber",
        "quarantined_unsafe": "badge-red",
        "decommission_recommended": "badge-red",
    }

    ASSESSMENT_TYPE_CSS = {
        "visual_inspection": "badge-slate",
        "ndt_ultrasonic": "badge-info",
        "ndt_thermography": "badge-amber",
        "ndt_vibration_pen": "badge-info",
        "ndt_dye_penetrant": "badge-amber",
        "ndt_magnetic_particle": "badge-amber",
        "oil_analysis": "badge-info",
        "diagnostic_checklist": "badge-slate",
    }

    title = models.CharField(
        max_length=255,
        help_text="Assessment summary or inspection scope title",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="condition_assessments",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="condition_assessments",
        help_text="Operational machinery or equipment record",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="condition_assessments",
        help_text="Asset category taxonomy",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_asset_condition_assessments",
        help_text="Internal technician or reliability examiner",
    )
    external_inspector = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracted_asset_condition_assessments",
        help_text="External accredited NDT agency or testing laboratory",
    )
    assessment_date = models.DateField(
        default=timezone.now,
        help_text="Date inspection was conducted",
    )
    assessment_type = models.CharField(
        max_length=32,
        choices=ASSESSMENT_TYPE_CHOICES,
        default="visual_inspection",
    )
    condition_grade = models.CharField(
        max_length=24,
        choices=CONDITION_GRADE_CHOICES,
        default="grade_2_good",
    )
    health_score = models.PositiveIntegerField(
        default=85,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Asset Health Index (0-100 score)",
    )
    operating_status = models.CharField(
        max_length=32,
        choices=OPERATING_STATUS_CHOICES,
        default="normal_operation",
    )
    checklist_summary = models.TextField(
        blank=True,
        help_text="Summary checklist inspection criteria evaluated",
    )
    findings = models.TextField(
        help_text="Detailed physical observations, wear patterns, or defect findings",
    )
    recommendations = models.TextField(
        blank=True,
        help_text="Recommended corrective actions, servicing, or operating restrictions",
    )
    followup_required = models.BooleanField(
        default=False,
        help_text="Flags that immediate corrective maintenance is required",
    )
    triggered_maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggering_condition_assessments",
        help_text="Corrective maintenance request generated from this assessment",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_asset_condition_assessments",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-assessment_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_acas_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "assessment_date"], name="idx_acas_ten_date"),
            models.Index(fields=["tenant", "condition_grade"], name="idx_acas_ten_grade"),
            models.Index(fields=["tenant", "status"], name="idx_acas_ten_stat"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_acas_ten_fa"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def condition_grade_css(self):
        return self.CONDITION_GRADE_CSS.get(self.condition_grade, "badge-slate")

    @property
    def operating_status_css(self):
        return self.OPERATING_STATUS_CSS.get(self.operating_status, "badge-slate")

    @property
    def assessment_type_css(self):
        return self.ASSESSMENT_TYPE_CSS.get(self.assessment_type, "badge-slate")
