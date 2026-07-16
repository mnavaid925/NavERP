"""HRM 3.23 Learning Management (LMS) — Learningprogress models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.models._base import _advance_months


class LearningProgress(TenantOwned):
    """Per-employee×course learning progress (3.23 Progress Tracking) — status/percent/time-spent, the
    assessment outcome (score/passed/attempts), and gamification ``points_earned``. Unique per
    (tenant, employee, course). Leaderboards + level tiers are DERIVED queries over ``points_earned``
    (no stored table). Reuses ``EmployeeProfile`` (learner) + ``TrainingCourse`` — no new tables."""

    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="learning_progress")
    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="learner_progress")
    learning_path = models.ForeignKey("hrm.LearningPath", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="progress_records", help_text="Enrolled via this path (optional).")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="not_started")
    percent_complete = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    time_spent_minutes = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    points_earned = models.PositiveIntegerField(default=0, help_text="Gamification points (leaderboard is derived).")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("tenant", "employee", "course")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_lprog_tenant_emp_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_lprog_tenant_course_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_lprog_tenant_status_idx"),
        ]

    def clean(self):
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValidationError({"completed_at": "Completion can't be before the start."})

    @property
    def certification_expires_on(self):
        """Derived (never stored) — the expiry date for a completed certification course, or None.
        Advances completed_at by the course's certification_validity_months with stdlib month-math
        (calendar.monthrange clamps the day) — no dateutil dependency."""
        if not (self.completed_at and self.course_id):
            return None
        course = self.course
        months = course.certification_validity_months
        if not (course.is_certification and months):
            return None
        return _advance_months(self.completed_at.date(), months)

    @property
    def is_certification_expired(self):
        exp = self.certification_expires_on
        return bool(exp and exp < timezone.now().date())

    def __str__(self):
        who = self.employee if self.employee_id else "?"
        what = self.course.title if self.course_id else "?"
        return f"{who} · {what} ({self.get_status_display()})"
