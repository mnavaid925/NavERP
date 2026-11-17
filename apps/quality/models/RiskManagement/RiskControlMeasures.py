from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class RiskControlMeasure(TenantNumbered):
    NUMBER_PREFIX = "QRCM"

    CONTROL_HIERARCHY_CHOICES = (
        ("inherent_safety", "1. Inherent Safety by Design"),
        ("protective_measure", "2. Protective Measures in Device/Process"),
        ("information_for_safety", "3. Information for Safety / Training"),
    )

    STATUS_CHOICES = (
        ("planned", "Planned / Under Design"),
        ("in_progress", "Implementation In Progress"),
        ("implemented", "Implemented / Ready for Verification"),
        ("verified", "Verified Effective"),
        ("ineffective", "Ineffective / Needs Revision"),
        ("obsolete", "Obsolete / Retired"),
    )

    CONTROL_HIERARCHY_CSS = {
        "inherent_safety": "badge-green",
        "protective_measure": "badge-info",
        "information_for_safety": "badge-amber",
    }

    STATUS_CSS = {
        "planned": "badge-slate",
        "in_progress": "badge-info",
        "implemented": "badge-amber",
        "verified": "badge-green",
        "ineffective": "badge-red",
        "obsolete": "badge-muted",
    }

    risk_assessment = models.ForeignKey(
        "quality.RiskAssessment",
        on_delete=models.CASCADE,
        related_name="control_measures",
    )
    control_hierarchy = models.CharField(
        max_length=28,
        choices=CONTROL_HIERARCHY_CHOICES,
        default="inherent_safety",
        help_text="ISO 14971 Clause 7.1 mandatory priority order",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(
        help_text="Engineering or procedural mitigation details",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_risk_controls",
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="planned",
        db_index=True,
    )

    # Spine Traceability Links
    design_input = models.ForeignKey(
        "quality.DesignInput",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_controls",
        help_text="Design requirement specifying this mitigation in Design Controls",
    )
    controlled_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_controls",
        help_text="SOP, work instruction, or IFU implementing this mitigation in Document Control",
    )
    design_verification = models.ForeignKey(
        "quality.DesignVerification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_controls",
        help_text="Test protocol verifying mitigation implementation and effectiveness",
    )

    # Verification & Safety Gate
    implementation_verified = models.BooleanField(
        default=False,
        help_text="ISO 14971 Clause 7.2 verification of implementation",
    )
    effectiveness_verified = models.BooleanField(
        default=False,
        help_text="ISO 14971 Clause 7.2 verification of effectiveness",
    )
    verification_notes = models.TextField(
        blank=True,
        help_text="Summary of objective verification evidence and test results",
    )
    introduces_new_hazard = models.BooleanField(
        default=False,
        help_text="ISO 14971 Clause 7.3 check for new hazards introduced by control",
    )
    new_hazard_details = models.TextField(
        blank=True,
        help_text="Description and cross-reference of any new hazard created",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Risk Control Measure"
        verbose_name_plural = "Risk Control Measures"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrcm_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "risk_assessment"], name="idx_qrcm_ten_assessment"),
            models.Index(fields=["tenant", "control_hierarchy"], name="idx_qrcm_ten_hier"),
            models.Index(fields=["tenant", "status"], name="idx_qrcm_ten_status"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qrcm_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def is_fully_verified(self):
        return self.implementation_verified and self.effectiveness_verified

    @property
    def control_hierarchy_badge(self):
        return self.CONTROL_HIERARCHY_CSS.get(self.control_hierarchy, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
