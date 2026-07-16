"""HRM 3.13 Salary Structure — Salarystructuretemplate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    JobGrade,
    SalaryStructureTemplate,
)


class SalaryStructureTemplateForm(TenantModelForm):
    class Meta:
        model = SalaryStructureTemplate
        fields = ["name", "job_grade", "annual_ctc_amount", "currency", "is_active", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Offer only active grades (the base form already tenant-scopes the FK).
        if self.tenant is not None and "job_grade" in self.fields:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order", "name"))
