"""HRM 3.2 Organizational Structure — Jobgrade forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    JobGrade,
)


# ----------------------------------------------------------------------- 3.2 Organizational Structure
class JobGradeForm(TenantModelForm):
    class Meta:
        model = JobGrade
        fields = ["name", "level_order", "description", "is_active"]
