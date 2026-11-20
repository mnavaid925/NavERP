import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CompetencyCertification(TenantNumbered):
    NUMBER_PREFIX = "QCERT"

    QUALIFICATION_LEVEL_CHOICES = (
        ("level_1_novice", "Level 1: Novice / Supervised Operator"),
        ("level_2_qualified", "Level 2: Fully Qualified / Independent"),
        ("level_3_senior_specialist", "Level 3: Senior Specialist / SME"),
        ("level_4_trainer_assessor", "Level 4: Certified Trainer / Assessor"),
    )

    STATUS_CHOICES = (
        ("active", "Active / Valid"),
        ("expiring_soon", "Expiring Soon (<30 Days)"),
        ("expired", "Expired"),
        ("suspended", "Suspended"),
        ("revoked", "Revoked"),
        ("superseded", "Superseded / Renewed"),
    )

    QUALIFICATION_LEVEL_CSS = {
        "level_1_novice": "badge-slate",
        "level_2_qualified": "badge-info",
        "level_3_senior_specialist": "badge-green",
        "level_4_trainer_assessor": "badge-amber",
    }

    STATUS_CSS = {
        "active": "badge-green",
        "expiring_soon": "badge-amber",
        "expired": "badge-red",
        "suspended": "badge-red",
        "revoked": "badge-red",
        "superseded": "badge-muted",
    }

    enrollment = models.ForeignKey(
        "quality.TrainingEnrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certifications",
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="competency_certifications",
    )
    course = models.ForeignKey(
        "quality.QualityTrainingCourse",
        on_delete=models.PROTECT,
        related_name="issued_certifications",
    )
    competency_matrix = models.ForeignKey(
        "quality.CompetencyMatrix",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certified_holders",
    )
    qualification_title = models.CharField(
        max_length=255,
        help_text="e.g. Certified Aseptic Fill Suite Level 2 Independent Operator",
    )
    qualification_level = models.CharField(
        max_length=32,
        choices=QUALIFICATION_LEVEL_CHOICES,
        default="level_2_qualified",
        db_index=True,
    )
    certificate_hash = models.CharField(
        max_length=64,
        editable=False,
        db_index=True,
        help_text="SHA-256 tamper-evident verification fingerprint",
    )
    issue_date = models.DateField(db_index=True)
    valid_until = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Certification expiration date (null if permanent)",
    )
    renewal_interval_months = models.PositiveSmallIntegerField(
        default=12,
        help_text="Renewal frequency in months e.g. 12 or 24",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active", db_index=True)
    authorized_work_centers = models.TextField(
        blank=True,
        help_text="Specific cleanroom suites, production lines, or equipment models authorized",
    )
    certified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authorized_competency_certifications",
    )
    electronic_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_certifications",
    )
    suspension_reason = models.TextField(
        blank=True,
        help_text="Documented rationale for certification suspension or revocation",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        verbose_name = "Competency Certification"
        verbose_name_plural = "Competency Certifications"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qcert_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qcert_ten_status"),
            models.Index(fields=["tenant", "trainee"], name="idx_qcert_ten_trainee"),
            models.Index(fields=["tenant", "course"], name="idx_qcert_ten_course"),
            models.Index(fields=["tenant", "valid_until"], name="idx_qcert_ten_valid"),
            models.Index(fields=["tenant", "qualification_level"], name="idx_qcert_ten_level"),
            models.Index(fields=["tenant", "certificate_hash"], name="idx_qcert_ten_hash"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qcert_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.qualification_title} ({self.trainee.username})"

    def generate_certificate_hash(self):
        seed = f"{getattr(self.tenant, 'pk', '')}:{self.trainee_id}:{self.course_id}:{self.issue_date}:{settings.SECRET_KEY}"
        return hashlib.sha256(seed.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if not self.certificate_hash:
            self.certificate_hash = self.generate_certificate_hash()
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        if self.status != "active":
            return False
        if self.valid_until and self.valid_until < timezone.now().date():
            return False
        return True

    @property
    def days_until_expiration(self):
        if self.valid_until:
            return (self.valid_until - timezone.now().date()).days
        return None

    @property
    def is_expiring_soon(self):
        days = self.days_until_expiration
        return days is not None and 0 <= days <= 30

    @property
    def is_expired(self):
        days = self.days_until_expiration
        return days is not None and days < 0

    @property
    def level_badge(self):
        return self.QUALIFICATION_LEVEL_CSS.get(self.qualification_level, "badge-slate")

    @property
    def status_badge(self):
        if self.is_expired and self.status == "active":
            return "badge-red"
        if self.is_expiring_soon and self.status == "active":
            return "badge-amber"
        return self.STATUS_CSS.get(self.status, "badge-slate")
