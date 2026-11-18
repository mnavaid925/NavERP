from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class LayeredProcessAudit(TenantNumbered):
    NUMBER_PREFIX = "QLPA"

    AUDIT_LAYER_CHOICES = [
        ("tier_1_operator_lead", "Tier 1: Shift Team Leader (Daily)"),
        ("tier_2_supervisor", "Tier 2: Area Production Supervisor (Weekly)"),
        ("tier_3_quality_manager", "Tier 3: Quality / Operations Manager (Monthly)"),
        ("tier_4_plant_executive", "Tier 4: Plant Manager / Director (Quarterly)"),
    ]

    FOCUS_AREA_CHOICES = [
        ("standard_work_wi", "Standard Work & Work Instruction Adherence"),
        ("tooling_machine_setup", "Machine Setup, Fixturing & Poka-Yoke"),
        ("material_handling_fifo", "Material Identification & FIFO / Lot Control"),
        ("gauging_calibration", "Measurement Gauging & Calibration Validity"),
        ("environmental_5s", "5S Housekeeping & Cleanliness"),
        ("safety_poka_yoke", "Operator Safety & Error-Proofing Verification"),
    ]

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    AUDIT_LAYER_CSS = {
        "tier_1_operator_lead": "badge-slate",
        "tier_2_supervisor": "badge-info",
        "tier_3_quality_manager": "badge-amber",
        "tier_4_plant_executive": "badge-green",
    }

    FOCUS_AREA_CSS = {
        "standard_work_wi": "badge-info",
        "tooling_machine_setup": "badge-slate",
        "material_handling_fifo": "badge-slate",
        "gauging_calibration": "badge-info",
        "environmental_5s": "badge-green",
        "safety_poka_yoke": "badge-amber",
    }

    STATUS_CSS = {
        "scheduled": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }

    title = models.CharField(max_length=255)
    audit_layer = models.CharField(
        max_length=30,
        choices=AUDIT_LAYER_CHOICES,
        default="tier_1_operator_lead",
        db_index=True,
    )
    focus_area = models.CharField(
        max_length=30,
        choices=FOCUS_AREA_CHOICES,
        default="standard_work_wi",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
        db_index=True,
    )

    work_center_code = models.CharField(max_length=64, blank=True)
    work_center = models.ForeignKey(
        "scm.WorkCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_lpas",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_lpas",
        help_text="Plant department or manufacturing division",
    )
    shift = models.CharField(
        max_length=32,
        blank=True,
        help_text="e.g. Shift 1 (Morning), Shift 2, Night",
    )

    total_questions_audited = models.PositiveIntegerField(default=10)
    questions_conforming = models.PositiveIntegerField(default=10)
    questions_non_conforming = models.PositiveIntegerField(default=0)
    compliance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        help_text="Calculated compliance score 0-100%",
    )
    findings_summary = models.TextField(blank=True)

    controlled_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lpa_audits",
        help_text="LPA Checklist or standard work instruction",
    )
    on_the_spot_mitigation = models.BooleanField(
        default=False,
        help_text="Identified non-conformances contained immediately during audit",
    )
    mitigation_details = models.TextField(blank=True)

    non_conformance = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lpas",
        help_text="Linked NCR if systemic non-conformance was observed",
    )
    auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_lpas",
    )
    scheduled_date = models.DateField()
    conducted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-created_at"]
        verbose_name = "Layered Process Audit"
        verbose_name_plural = "Layered Process Audits"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qlpa_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qlpa_ten_status"),
            models.Index(fields=["tenant", "audit_layer"], name="idx_qlpa_ten_layer"),
            models.Index(fields=["tenant", "focus_area"], name="idx_qlpa_ten_focus"),
            models.Index(fields=["tenant", "work_center"], name="idx_qlpa_ten_wc"),
            models.Index(fields=["tenant", "scheduled_date"], name="idx_qlpa_ten_sched"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qlpa_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_audit_layer_display()})"

    def save(self, *args, **kwargs):
        if self.total_questions_audited and self.total_questions_audited > 0:
            score = (Decimal(self.questions_conforming) / Decimal(self.total_questions_audited)) * Decimal("100.00")
            self.compliance_percentage = round(score, 2)
        super().save(*args, **kwargs)

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def layer_css(self):
        return self.AUDIT_LAYER_CSS.get(self.audit_layer, "badge-slate")

    @property
    def focus_css(self):
        return self.FOCUS_AREA_CSS.get(self.focus_area, "badge-slate")

    @property
    def compliance_rate_display(self):
        return f"{self.compliance_percentage}%"

    @property
    def is_passing(self):
        return self.compliance_percentage >= Decimal("90.00")
