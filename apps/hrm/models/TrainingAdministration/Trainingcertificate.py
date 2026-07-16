"""HRM 3.24 Training Administration — Trainingcertificate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.models._base import _advance_months


class TrainingCertificate(TenantNumbered):
    """A completion-certificate issuance record (3.24 Certificates) — issued from a completed ILT
    ``TrainingAttendance`` OR a completed LMS ``LearningProgress`` (or manually). ``expires_on`` is
    computed ONCE at ``save()`` (the issued artifact must not drift if the course's validity changes
    later); ``verification_code`` is a one-shot random token. Revoke instead of delete for an issued
    certificate (audit trail)."""

    NUMBER_PREFIX = "CERT"

    STATUS_CHOICES = [
        ("issued", "Issued"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="training_certificates")
    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="certificates")
    source_attendance = models.ForeignKey("hrm.TrainingAttendance", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="certificates_issued")
    source_progress = models.ForeignKey("hrm.LearningProgress", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="certificates_issued")
    title = models.CharField(max_length=255, blank=True, help_text="Defaults from the course's certification name.")
    issued_on = models.DateField(default=timezone.localdate)
    expires_on = models.DateField(null=True, blank=True, editable=False,
                                  help_text="Computed once from issued_on + the course's validity months.")
    verification_code = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="issued")
    revoked_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_on"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_cert_tenant_emp_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_cert_tenant_course_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_cert_tenant_status_idx"),
        ]

    def clean(self):
        if self.source_attendance_id and self.source_progress_id:
            raise ValidationError({"source_progress": "Link only one source — attendance OR progress, not both."})
        if self.source_attendance_id:
            att = self.source_attendance
            if att.employee_id != self.employee_id or (att.session_id and att.session.course_id != self.course_id):
                raise ValidationError({"source_attendance": "Source attendance is for a different employee/course."})
        if self.source_progress_id:
            prog = self.source_progress
            if prog.employee_id != self.employee_id or prog.course_id != self.course_id:
                raise ValidationError({"source_progress": "Source progress is for a different employee/course."})

    def save(self, *args, **kwargs):
        if not self.title and self.course_id:
            self.title = self.course.certification_name or self.course.title
        if not self.verification_code:
            self.verification_code = secrets.token_hex(8).upper()   # 16 hex chars, 64 bits of entropy
        # Recompute expires_on from issued_on on every save (so correcting a typo'd issued_on fixes the
        # expiry too) — from the course's current validity window, or cleared if the course isn't a
        # certification / has no validity set.
        if self.issued_on and self.course_id:
            months = self.course.certification_validity_months
            self.expires_on = (_advance_months(self.issued_on, months)
                               if (self.course.is_certification and months) else None)
        return super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Live truth (derived) — a stored status='expired' is never auto-flipped this pass (no cron),
        so templates/badges must render off THIS, not solely off status."""
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.title}" if self.number else self.title
