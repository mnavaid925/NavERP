"""HRM 3.13 Salary Structure — Employeesalarystructure forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeSalaryStructure,
    SalaryStructureTemplate,
)


class EmployeeSalaryStructureForm(TenantModelForm):
    class Meta:
        model = EmployeeSalaryStructure
        fields = ["employee", "template", "annual_ctc_amount", "effective_from", "effective_to",
                  "status", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # employee is tenant-scoped + name-ordered by the base form / EmployeeProfile.Meta.
        if self.tenant is not None and "template" in self.fields:
            self.fields["template"].queryset = (
                SalaryStructureTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
