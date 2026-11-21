from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class DataIntegrityAssessment(TenantNumbered):
    NUMBER_PREFIX = "QDIR"

    ALCOA_RATING_CHOICES = [
        ("fully_compliant", "Fully Compliant (Technical Controls)"),
        ("partially_compliant", "Partially Compliant (Procedural Safeguards)"),
        ("non_compliant", "Non-Compliant (Identified Vulnerability)"),
        ("not_applicable", "Not Applicable / Out of Scope"),
    ]

    RISK_LEVEL_CHOICES = [
        ("low", "Low Risk (Negligible GxP/Product Impact)"),
        ("medium", "Medium Risk (Procedural Safeguards in Place)"),
        ("high", "High Risk (Direct Quality / Release Vulnerability)"),
        ("critical", "Critical Risk (Data Falsification / Uncontrolled Edit)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Assessment"),
        ("in_assessment", "Active Assessment / Review"),
        ("remediation_pending", "Remediation Plan Pending"),
        ("approved", "QA Approved & Closed"),
        ("superseded", "Superseded by Periodic Review"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_assessment": "badge-info",
        "remediation_pending": "badge-amber",
        "approved": "badge-green",
        "superseded": "badge-muted",
    }

    RISK_LEVEL_CSS = {
        "low": "badge-green",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    title = models.CharField(max_length=255)
    assessment_scope = models.CharField(
        max_length=150, help_text="Workflow, instrument, or system evaluated"
    )
    system = models.ForeignKey(
        "quality.ComputerSystemValidation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="data_integrity_assessments",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="data_integrity_assessments",
    )
    lead_assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_di_assessments",
    )
    qa_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_di_assessments",
    )
    assessment_date = models.DateField(null=True, blank=True)
    next_review_due = models.DateField(null=True, blank=True)

    # ALCOA+ 9 Dimensions
    attributable_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    legible_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    contemporaneous_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    original_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    accurate_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    complete_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    consistent_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    enduring_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )
    available_rating = models.CharField(
        max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant"
    )

    overall_risk_level = models.CharField(
        max_length=20, choices=RISK_LEVEL_CHOICES, default="low", db_index=True
    )
    vulnerabilities_summary = models.TextField(
        blank=True, help_text="Identified data integrity gaps or risks"
    )
    remediation_plan = models.TextField(
        blank=True, help_text="Corrective and preventive controls planned"
    )
    linked_capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="di_assessments",
    )
    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="di_assessments",
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True
    )
    qa_approved_at = models.DateTimeField(null=True, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Data Integrity Assessment"
        verbose_name_plural = "Data Integrity Assessments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qdir_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "overall_risk_level", "status"], name="idx_qdir_ten_rsk_stat"),
            models.Index(fields=["tenant", "next_review_due"], name="idx_qdir_ten_rev_due"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def non_compliant_count(self):
        ratings = [
            self.attributable_rating,
            self.legible_rating,
            self.contemporaneous_rating,
            self.original_rating,
            self.accurate_rating,
            self.complete_rating,
            self.consistent_rating,
            self.enduring_rating,
            self.available_rating,
        ]
        return ratings.count("non_compliant")

    @property
    def is_high_risk(self):
        return self.overall_risk_level in ["high", "critical"]

    @property
    def is_overdue(self):
        return bool(
            self.next_review_due
            and self.next_review_due < timezone.now().date()
            and self.status != "approved"
        )
