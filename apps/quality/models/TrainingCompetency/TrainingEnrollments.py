from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class TrainingEnrollment(TenantNumbered):
    NUMBER_PREFIX = "QENR"

    ASSIGNMENT_REASON_CHOICES = (
        ("onboarding_new_hire", "New Hire / Onboarding Qualification"),
        ("annual_refresher", "Annual / Periodic Refresher Training"),
        ("dco_revision_retrain", "Document Revision (DCO) Retraining"),
        ("capa_corrective_action", "CAPA Corrective Action Retraining"),
        ("role_transfer", "Role Change / Promotion Transfer"),
        ("manager_assignment", "Manager / Supervisor Assignment"),
        ("remediation_retrain", "Remediation / Failed Attempt Retrain"),
    )

    STATUS_CHOICES = (
        ("assigned", "Assigned / Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed (Pending Verification)"),
        ("verified", "Verified / Qualified"),
        ("overdue", "Overdue"),
        ("waived", "Waived / Exempt"),
        ("failed", "Failed Assessment"),
    )

    PRACTICAL_RATING_CHOICES = (
        ("exceeds_standard", "Exceeds Standard"),
        ("meets_standard", "Meets Standard (Proficient)"),
        ("needs_improvement", "Needs Improvement"),
        ("unsatisfactory", "Unsatisfactory / Not Qualified"),
    )

    ASSIGNMENT_REASON_CSS = {
        "onboarding_new_hire": "badge-info",
        "annual_refresher": "badge-slate",
        "dco_revision_retrain": "badge-amber",
        "capa_corrective_action": "badge-red",
        "role_transfer": "badge-info",
        "manager_assignment": "badge-slate",
        "remediation_retrain": "badge-amber",
    }

    STATUS_CSS = {
        "assigned": "badge-info",
        "in_progress": "badge-amber",
        "completed": "badge-info",
        "verified": "badge-green",
        "overdue": "badge-red",
        "waived": "badge-muted",
        "failed": "badge-red",
    }

    PRACTICAL_RATING_CSS = {
        "exceeds_standard": "badge-green",
        "meets_standard": "badge-info",
        "needs_improvement": "badge-amber",
        "unsatisfactory": "badge-red",
    }

    course = models.ForeignKey(
        "quality.QualityTrainingCourse",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quality_training_enrollments",
    )
    assignment_reason = models.CharField(
        max_length=32,
        choices=ASSIGNMENT_REASON_CHOICES,
        default="manager_assignment",
        db_index=True,
    )
    document_change_order = models.ForeignKey(
        "quality.DocumentChangeOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_enrollments",
    )
    capa_action = models.ForeignKey(
        "quality.CapaAction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_training_enrollments",
    )
    assigned_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="assigned", db_index=True)

    completion_date = models.DateField(null=True, blank=True)
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Exam score percentage e.g. 95.00",
    )
    is_passed = models.BooleanField(default=False)
    self_certified = models.BooleanField(
        default=False,
        help_text="Trainee confirmation of reading/understanding or course completion",
    )
    self_certified_at = models.DateTimeField(null=True, blank=True)

    practical_evaluation_notes = models.TextField(
        blank=True,
        help_text="Supervisor practical OJT evaluation observations",
    )
    practical_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_practical_trainings",
    )
    practical_verified_at = models.DateTimeField(null=True, blank=True)
    practical_rating = models.CharField(
        max_length=24,
        choices=PRACTICAL_RATING_CHOICES,
        null=True,
        blank=True,
    )

    waiver_reason = models.TextField(
        blank=True,
        help_text="Formal regulatory justification for waiver or exemption",
    )
    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waived_training_enrollments",
    )
    waived_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assigned_date", "-created_at"]
        verbose_name = "Training Enrollment"
        verbose_name_plural = "Training Enrollments"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qenr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qenr_ten_status"),
            models.Index(fields=["tenant", "trainee"], name="idx_qenr_ten_trainee"),
            models.Index(fields=["tenant", "course"], name="idx_qenr_ten_course"),
            models.Index(fields=["tenant", "due_date"], name="idx_qenr_ten_due"),
            models.Index(fields=["tenant", "assignment_reason"], name="idx_qenr_ten_reason"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qenr_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.course.title} ({self.trainee.username})"

    @property
    def is_overdue(self):
        if self.status in ("assigned", "in_progress") and self.due_date:
            return self.due_date < timezone.now().date()
        return False

    @property
    def days_remaining(self):
        if self.due_date:
            return (self.due_date - timezone.now().date()).days
        return 0

    @property
    def reason_badge(self):
        return self.ASSIGNMENT_REASON_CSS.get(self.assignment_reason, "badge-slate")

    @property
    def status_badge(self):
        if self.is_overdue and self.status in ("assigned", "in_progress"):
            return "badge-red"
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def practical_rating_badge(self):
        return self.PRACTICAL_RATING_CSS.get(self.practical_rating, "badge-slate")

    @property
    def requires_practical_verification(self):
        return (
            self.course.assessment_method in ("practical_ojt", "both_exam_and_ojt")
            and self.practical_verified_at is None
        )
