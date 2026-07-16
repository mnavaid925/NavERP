"""HRM 3.3 Employee Onboarding — Orientationsession models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeOnboarding.Program import OnboardingProgram
from apps.hrm.models.EmployeeOnboarding.Program import OnboardingProgram


class OrientationSession(TenantOwned):
    """A scheduled orientation / training / meet-and-greet for a new hire (3.3). ``program`` is
    nullable for ad-hoc sessions. ``meeting_url`` supports virtual sessions; ``attendance_status``
    tracks completion without full calendar integration."""

    SESSION_TYPE_CHOICES = [
        ("orientation", "Orientation"),
        ("training", "Training"),
        ("meet_greet", "Meet & Greet"),
        ("policy_review", "Policy Review"),
        ("system_demo", "System Demo"),
        ("department_intro", "Department Intro"),
        ("social", "Social / Team Lunch"),
        ("custom", "Custom"),
    ]
    ATTENDANCE_STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("attended", "Attended"),
        ("missed", "Missed"),
        ("rescheduled", "Rescheduled"),
        ("cancelled", "Cancelled"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.SET_NULL, null=True, blank=True, related_name="orientation_sessions")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="orientation_sessions")
    title = models.CharField(max_length=255)
    session_type = models.CharField(max_length=30, choices=SESSION_TYPE_CHOICES, default="orientation")
    facilitator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="facilitated_orientation_sessions")
    facilitator_name = models.CharField(max_length=255, blank=True, help_text="Free-text fallback for an external trainer with no user account.")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(blank=True)
    attendance_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default="scheduled")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_ors_tenant_emp_idx"),
            models.Index(fields=["tenant", "program"], name="hrm_ors_tenant_prog_idx"),
            models.Index(fields=["tenant", "scheduled_at"], name="hrm_ors_tenant_sched_idx"),
            models.Index(fields=["tenant", "attendance_status"], name="hrm_ors_tenant_attst_idx"),
        ]

    def clean(self):
        super().clean()
        # A program session can't be scheduled before the hire even starts. Fetch only the start
        # date (not the whole program row) to keep this validation path light.
        if self.program_id and self.scheduled_at:
            start = (OnboardingProgram.objects.filter(pk=self.program_id)
                     .values_list("start_date", flat=True).first())
            if start and self.scheduled_at.date() < start:
                raise ValidationError({"scheduled_at": "Session cannot be scheduled before the program start date."})

    def __str__(self):
        return f"{self.title} @ {self.scheduled_at:%Y-%m-%d %H:%M}" if self.scheduled_at else self.title
