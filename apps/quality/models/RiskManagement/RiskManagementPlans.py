from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class RiskManagementPlan(TenantNumbered):
    NUMBER_PREFIX = "QRMP"

    STATUS_CHOICES = (
        ("draft", "Draft / Scoping"),
        ("in_review", "In Review"),
        ("active", "Active / Effective"),
        ("periodic_review", "Under Periodic Review"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    )

    DEVICE_CLASSIFICATION_CHOICES = (
        ("class_i", "Class I (Low Risk)"),
        ("class_ii_a", "Class IIa (Moderate Risk)"),
        ("class_ii_b", "Class IIb (High-Moderate Risk)"),
        ("class_iii", "Class III (High Risk - Critical)"),
        ("samd", "SaMD / Digital Health"),
        ("non_medical", "Non-Medical Regulated Product"),
    )

    MATRIX_DIMENSION_CHOICES = (
        ("3x3", "3 x 3 Matrix (Low/Med/High)"),
        ("4x4", "4 x 4 Matrix"),
        ("5x5", "5 x 5 Matrix (Standard ISO 14971)"),
    )

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "active": "badge-green",
        "periodic_review": "badge-info",
        "superseded": "badge-muted",
        "archived": "badge-muted",
    }

    DEVICE_CLASS_CSS = {
        "class_i": "badge-slate",
        "class_ii_a": "badge-info",
        "class_ii_b": "badge-amber",
        "class_iii": "badge-red",
        "samd": "badge-info",
        "non_medical": "badge-slate",
    }

    title = models.CharField(max_length=255)
    plan_version = models.CharField(max_length=16, default="1.0")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)

    design_project = models.ForeignKey(
        "quality.DesignProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_plans",
        help_text="Associated product development plan in Design Controls",
    )
    lead_risk_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_risk_plans",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_plans",
    )
    device_classification = models.CharField(
        max_length=24,
        choices=DEVICE_CLASSIFICATION_CHOICES,
        default="class_ii_a",
    )
    scope_description = models.TextField(
        help_text="Device description, clinical intended use, and lifecycle boundaries",
    )
    matrix_dimension = models.CharField(
        max_length=12,
        choices=MATRIX_DIMENSION_CHOICES,
        default="5x5",
    )
    risk_acceptability_policy = models.TextField(
        help_text="Documented criteria for risk acceptability, ALARP thresholds, and evaluation policy",
    )
    overall_residual_risk_acceptable = models.BooleanField(
        default=False,
        help_text="Certification per ISO 14971 Clause 8",
    )
    overall_benefit_risk_summary = models.TextField(
        blank=True,
        help_text="Executive summary justifying that overall clinical benefits outweigh collective residual risks",
    )
    periodic_review_frequency_months = models.PositiveSmallIntegerField(
        default=12,
        help_text="Review frequency in months (e.g. 12)",
    )
    next_review_due_date = models.DateField(null=True, blank=True)
    approved_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_risk_plans",
        editable=False,
        help_text="21 CFR Part 11 signature manifest",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Risk Management Plan"
        verbose_name_plural = "Risk Management Plans"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrmp_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qrmp_ten_status"),
            models.Index(fields=["tenant", "device_classification"], name="idx_qrmp_ten_class"),
            models.Index(fields=["tenant", "design_project"], name="idx_qrmp_ten_prj"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qrmp_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} (v{self.plan_version})"

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def device_class_badge(self):
        return self.DEVICE_CLASS_CSS.get(self.device_classification, "badge-slate")

    @property
    def is_review_overdue(self):
        if not self.next_review_due_date or self.status not in ("active", "periodic_review"):
            return False
        return self.next_review_due_date < timezone.now().date()

    @property
    def assessments_count(self):
        return self.assessments.count()

    @property
    def unmitigated_risks_count(self):
        return self.assessments.filter(residual_risk_acceptable=False).count()
