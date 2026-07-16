"""HRM 3.3 Employee Onboarding — Templatetask models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeOnboarding.ASSIGNEE_ROLE_CHOICESs import ASSIGNEE_ROLE_CHOICES
from apps.hrm.models.EmployeeOnboarding.PHASE_CHOICESs import PHASE_CHOICES
from apps.hrm.models.EmployeeOnboarding.Task import TASK_CATEGORY_CHOICES
from apps.hrm.models.EmployeeOnboarding.ASSIGNEE_ROLE_CHOICESs import ASSIGNEE_ROLE_CHOICES
from apps.hrm.models.EmployeeOnboarding.PHASE_CHOICESs import PHASE_CHOICES
from apps.hrm.models.EmployeeOnboarding.Task import TASK_CATEGORY_CHOICES


class OnboardingTemplateTask(TenantOwned):
    """One task definition line inside an ``OnboardingTemplate`` (3.3). ``due_offset_days`` is
    relative to the hire's start date (negative = preboarding, 0 = day one, positive = after)."""

    template = models.ForeignKey("hrm.OnboardingTemplate", on_delete=models.CASCADE, related_name="template_tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_category = models.CharField(max_length=30, choices=TASK_CATEGORY_CHOICES, default="custom")
    assignee_role = models.CharField(max_length=20, choices=ASSIGNEE_ROLE_CHOICES, default="hr")
    due_offset_days = models.IntegerField(default=0, help_text="Days relative to start date (negative = before, 0 = first day, positive = after).")
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default="week_1")
    order = models.PositiveIntegerField(default=0)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["template", "phase", "order", "title"]
        unique_together = ("tenant", "template", "title")
        indexes = [
            models.Index(fields=["tenant", "template"], name="hrm_ontt_tenant_tmpl_idx"),
            models.Index(fields=["tenant", "template", "phase"], name="hrm_ontt_tenant_tmpl_phase_idx"),
        ]

    def __str__(self):
        return f"{self.template} → {self.title}"
