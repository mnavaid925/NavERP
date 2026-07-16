"""HRM 3.3 Employee Onboarding — Templatetask forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingTemplateTask,
)


class OnboardingTemplateTaskForm(TenantModelForm):
    class Meta:
        model = OnboardingTemplateTask
        fields = ["template", "title", "description", "task_category", "assignee_role",
                  "due_offset_days", "phase", "order", "is_mandatory"]
