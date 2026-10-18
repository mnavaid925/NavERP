"""Sales 8.9 — `SalesCertification` (`SCTF-`), sales readiness, curricula and rep accreditation.

Tracks onboarding curricula, product certifications, sales methodologies (MEDDPICC, Challenger),
compliance/security exams, and demo accreditations with scoring and expiration dates.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

CERTIFICATION_CATEGORY_CHOICES = [
    ("onboarding", "New Rep Onboarding Curriculum"),
    ("product_certification", "Product / Solution Certification"),
    ("methodology", "Sales Methodology (MEDDPICC, Challenger, SPICED)"),
    ("compliance", "Security, Privacy & Regulatory Compliance"),
    ("pitch_accreditation", "Pitch & Demo Accreditation"),
]

CERTIFICATION_STATUS_CHOICES = [
    ("enrolled", "Enrolled / In Progress"),
    ("completed", "Completed / Passed"),
    ("failed", "Failed / Requires Retake"),
    ("expired", "Expired"),
]


class SalesCertification(TenantNumbered):
    NUMBER_PREFIX = "SCTF"

    curriculum_name = models.CharField(max_length=150, db_index=True)
    category = models.CharField(
        max_length=30,
        choices=CERTIFICATION_CATEGORY_CHOICES,
        default="product_certification",
        db_index=True,
    )
    rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_certifications",
    )
    status = models.CharField(
        max_length=20,
        choices=CERTIFICATION_STATUS_CHOICES,
        default="enrolled",
        db_index=True,
    )
    score_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Achieved exam or rubric score (0.00 to 100.00%).",
    )
    passing_score_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("80.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Minimum score required to pass (default 80.00%).",
    )
    certified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_sales_certifications",
    )
    certified_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(
        null=True,
        blank=True,
        help_text="Certification expiration date requiring recertification.",
    )
    accreditation_notes = models.TextField(blank=True)
    hrm_course = models.ForeignKey(
        "hrm.TrainingCourse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_certifications",
    )

    class Meta:
        ordering = ["-certified_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_sctf_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "category", "status"],
                name="sales_sctf_cat_stat_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.curriculum_name} ({self.rep}) [{self.get_status_display()}]"

    def clean(self):
        super().clean()
        if self.score_percent is not None:
            if self.score_percent < Decimal("0.00") or self.score_percent > Decimal("100.00"):
                raise ValidationError({"score_percent": "Score must be between 0.00% and 100.00%."})

        if self.passing_score_percent < Decimal("0.00") or self.passing_score_percent > Decimal("100.00"):
            raise ValidationError({"passing_score_percent": "Passing score must be between 0.00% and 100.00%."})

        if self.status == "completed":
            if self.score_percent is not None and self.score_percent < self.passing_score_percent:
                raise ValidationError(
                    {"status": f"Score {self.score_percent}% is below passing threshold {self.passing_score_percent}%; cannot mark Completed."}
                )
            if not self.certified_at:
                self.certified_at = timezone.now().date()

        if self.expires_at and self.certified_at and self.expires_at < self.certified_at:
            raise ValidationError({"expires_at": "Expiration date cannot precede certification date."})

        if self.hrm_course_id and self.tenant_id:
            if getattr(self.hrm_course, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"hrm_course": "Associated HRM training course must belong to the same workspace."})

        if self.rep_id and self.tenant_id:
            if getattr(self.rep, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"rep": "Assigned representative must belong to the same workspace."})

        if self.certified_by_id and self.tenant_id:
            if getattr(self.certified_by, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"certified_by": "Certifying user must belong to the same workspace."})

