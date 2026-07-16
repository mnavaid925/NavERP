"""HRM 3.3 Employee Onboarding — Task models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeOnboarding.ASSIGNEE_ROLE_CHOICESs import ASSIGNEE_ROLE_CHOICES
from apps.hrm.models.EmployeeOnboarding.PHASE_CHOICESs import PHASE_CHOICES
from apps.hrm.models.EmployeeOnboarding.ASSIGNEE_ROLE_CHOICESs import ASSIGNEE_ROLE_CHOICES
from apps.hrm.models.EmployeeOnboarding.PHASE_CHOICESs import PHASE_CHOICES


# Shared choice sets — referenced by both the template task definition and the concrete
# per-program task, so the taxonomy stays identical between the two (module-level = single source).
TASK_CATEGORY_CHOICES = [
    ("hr_admin", "HR Admin"),
    ("it_setup", "IT Setup"),
    ("manager_action", "Manager Action"),
    ("buddy_action", "Buddy Action"),
    ("new_hire_action", "New Hire Action"),
    ("document_sign", "Document Sign"),
    ("equipment_request", "Equipment Request"),
    ("training", "Training"),
    ("meet_greet", "Meet & Greet"),
    ("custom", "Custom"),
]


class OnboardingTask(TenantOwned):
    """A concrete task on one ``OnboardingProgram`` (3.3). Generated from the template's task
    lines (due_date = program.start_date + offset) or added ad-hoc. ``completed_at`` /
    ``completed_by`` are system-set by the complete action, never on the form."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_category = models.CharField(max_length=30, choices=TASK_CATEGORY_CHOICES, default="custom")
    assignee_role = models.CharField(max_length=20, choices=ASSIGNEE_ROLE_CHOICES, default="hr")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_onboarding_tasks")
    due_date = models.DateField(null=True, blank=True)
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default="week_1")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_mandatory = models.BooleanField(default=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="completed_onboarding_tasks", editable=False)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["program", "phase", "order", "due_date"]
        indexes = [
            models.Index(fields=["tenant", "program"], name="hrm_ont_tenant_prog_idx"),
            models.Index(fields=["tenant", "program", "status"], name="hrm_ont_tenant_prog_status_idx"),
            models.Index(fields=["tenant", "program", "phase"], name="hrm_ont_tenant_prog_phase_idx"),
        ]

    def is_overdue(self):
        """True when an unresolved task's due date has passed (display-only helper)."""
        return bool(self.due_date and self.status in ("pending", "in_progress")
                    and self.due_date < date.today())

    def __str__(self):
        return f"{self.program} → {self.title}"
