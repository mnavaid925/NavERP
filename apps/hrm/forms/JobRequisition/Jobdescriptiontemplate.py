"""HRM 3.5 Job Requisition — Jobdescriptiontemplate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    JobDescriptionTemplate,
)


# ----------------------------------------------------------------------- 3.5 Job Requisition
class JobDescriptionTemplateForm(TenantModelForm):
    class Meta:
        model = JobDescriptionTemplate
        fields = ["name", "designation", "employment_type", "jd_summary", "jd_responsibilities",
                  "jd_requirements", "jd_nice_to_have", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["designation"].queryset = (
                Designation.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
