"""core — Employment forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    Employment,
)


class EmploymentForm(TenantModelForm):
    class Meta:
        model = Employment
        fields = ["party", "org_unit", "manager", "job_title", "hired_on", "status"]
