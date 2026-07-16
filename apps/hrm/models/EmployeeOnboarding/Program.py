"""HRM 3.3 Employee Onboarding — Program models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class OnboardingProgram(TenantNumbered):
    """A template applied to one new hire (3.3) — the per-employee onboarding instance.
    ``progress`` is derived from its tasks (spine principle: never stored). The Welcome Kit
    (3.3) is the ``welcome_*`` / ``first_day_notes`` fields here — no separate table."""

    NUMBER_PREFIX = "ONB"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="onboarding_programs")
    template = models.ForeignKey("hrm.OnboardingTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="programs")
    start_date = models.DateField(help_text="The new hire's first day — drives every task due date.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    buddy = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="buddy_for")
    welcome_message = models.TextField(blank=True)
    welcome_video_url = models.URLField(blank=True)
    first_day_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_onb_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_onb_tenant_status_idx"),
            models.Index(fields=["tenant", "start_date"], name="hrm_onb_tenant_start_idx"),
        ]

    @property
    def progress(self):
        """Percent of tasks resolved (0–100). Derived — never stored. Skipped tasks count as
        resolved so an all-skipped program reads as 100% done, not stuck. List views use the
        ``tasks_total``/``tasks_done`` annotations (no N+1); the detail view computes this from its
        already-fetched task list. Memoised so an accidental second call doesn't re-query."""
        if not hasattr(self, "_progress_cache"):
            total = self.tasks.count()
            if total:
                done = self.tasks.filter(status__in=("completed", "skipped")).count()
                self._progress_cache = int(round(done / total * 100))
            else:
                self._progress_cache = 0
        return self._progress_cache

    def __str__(self):
        return f"{self.number} · {self.employee}" if self.number else str(self.employee)
