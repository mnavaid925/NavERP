"""HRM 3.23 Learning Management (LMS) — Learningpath forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningPath,
)


class LearningPathForm(TenantModelForm):
    # target_designation/target_department are auto tenant-scoped by TenantModelForm; the model's
    # limit_choices_to={"kind": "department"} narrows the department dropdown to department OrgUnits.
    class Meta:
        model = LearningPath
        fields = ["title", "description", "target_designation", "target_department",
                  "is_mandatory", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }
