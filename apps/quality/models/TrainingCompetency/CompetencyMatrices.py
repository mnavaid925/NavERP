from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class CompetencyMatrix(TenantNumbered):
    NUMBER_PREFIX = "QMTX"

    QUALIFICATION_TIER_CHOICES = (
        ("trainee", "Trainee (Supervised Only)"),
        ("independent", "Independent Operator / Qualified"),
        ("specialist", "Senior Specialist / SME"),
        ("trainer", "Certified Trainer / Assessor"),
        ("auditor", "Qualified Internal Auditor"),
    )

    CRITICALITY_CHOICES = (
        ("low", "Low / General Admin"),
        ("medium", "Medium / Standard Operating"),
        ("high", "High / Direct Product Contact"),
        ("critical_gxp", "Critical GxP / Sterility Assurance"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("active", "Active"),
        ("retired", "Retired"),
    )

    QUALIFICATION_TIER_CSS = {
        "trainee": "badge-slate",
        "independent": "badge-info",
        "specialist": "badge-green",
        "trainer": "badge-amber",
        "auditor": "badge-info",
    }

    CRITICALITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical_gxp": "badge-red",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "approved": "badge-info",
        "active": "badge-green",
        "retired": "badge-muted",
    }

    title = models.CharField(max_length=255, help_text="e.g. Aseptic Fill Line Operator Competency Matrix")
    role_title = models.CharField(max_length=128, help_text="Target role or job position e.g. Cleanroom Technician")
    qualification_tier = models.CharField(
        max_length=24,
        choices=QUALIFICATION_TIER_CHOICES,
        default="independent",
        db_index=True,
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competency_matrices",
    )
    criticality = models.CharField(
        max_length=24,
        choices=CRITICALITY_CHOICES,
        default="medium",
        db_index=True,
    )
    revision = models.CharField(max_length=16, default="1.0", help_text="Revision/version identifier")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft", db_index=True)
    minimum_passing_score = models.PositiveSmallIntegerField(
        default=80,
        help_text="Passing threshold percentage e.g. 80",
    )
    validity_period_months = models.PositiveSmallIntegerField(
        default=12,
        help_text="Re-qualification cycle in months e.g. 12",
    )
    prerequisite_experience_months = models.PositiveSmallIntegerField(
        default=0,
        help_text="Required months of domain experience",
    )
    description = models.TextField(blank=True, help_text="Curriculum overview and qualification scope")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_competency_matrices",
    )
    approval_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Competency Matrix"
        verbose_name_plural = "Competency Matrices"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qmtx_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qmtx_ten_status"),
            models.Index(fields=["tenant", "qualification_tier"], name="idx_qmtx_ten_tier"),
            models.Index(fields=["tenant", "criticality"], name="idx_qmtx_ten_crit"),
            models.Index(fields=["tenant", "department"], name="idx_qmtx_ten_dept"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qmtx_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} (v{self.revision})"

    @property
    def tier_badge(self):
        return self.QUALIFICATION_TIER_CSS.get(self.qualification_tier, "badge-slate")

    @property
    def criticality_badge(self):
        return self.CRITICALITY_CSS.get(self.criticality, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def courses_count(self):
        return self.courses.count()

    @property
    def active_courses_count(self):
        return self.courses.filter(status="active").count()

    @property
    def certifications_count(self):
        return self.certified_holders.filter(status="active").count()
