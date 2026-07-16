"""HRM 3.3 Employee Onboarding — Task forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingTask,
)


class OnboardingTaskForm(TenantModelForm):
    # SECURITY: `status`, `completed_at`, `completed_by` are excluded — task status is advanced
    # only by the complete/reopen/skip workflow actions (which stamp who/when).
    class Meta:
        model = OnboardingTask
        fields = ["program", "title", "description", "task_category", "assignee_role", "assignee",
                  "due_date", "phase", "is_mandatory", "order", "notes"]
