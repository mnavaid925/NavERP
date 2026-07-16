"""HRM 3.5 Job Requisition — Jobrequisition forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    JobDescriptionTemplate,
    JobGrade,
    JobRequisition,
)


class JobRequisitionForm(TenantModelForm):
    # SECURITY: the workflow-owned fields (`status`, `submitted_at`, `approved_at`, `posted_at`,
    # `filled_at`) and the auto `number` are excluded — advanced only by the audited POST actions.
    # Mirrors the SeparationCaseForm exclusion pattern (prevents status forging via a crafted POST).
    class Meta:
        model = JobRequisition
        fields = ["title", "designation", "job_grade", "template", "department", "cost_center",
                  "location", "headcount", "req_type", "employment_type", "reason_for_hire",
                  "is_replacement_for", "posting_type", "hiring_manager", "recruiter",
                  "target_start_date", "priority", "salary_min", "salary_max", "salary_currency",
                  "estimated_annual_cost", "hiring_cost_budget", "jd_summary", "jd_responsibilities",
                  "jd_requirements", "jd_nice_to_have", "notes"]
        widgets = {"target_start_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["designation"].queryset = (
                Designation.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("level_order", "name"))
            self.fields["template"].queryset = (
                JobDescriptionTemplate.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("name"))
            self.fields["department"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            self.fields["cost_center"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center").order_by("name"))
            employees = (EmployeeProfile.objects.filter(tenant=self.tenant)
                         .select_related("party").order_by("party__name"))
            self.fields["hiring_manager"].queryset = employees
            self.fields["recruiter"].queryset = employees

    def clean(self):
        cleaned = super().clean()
        salary_min = cleaned.get("salary_min")
        salary_max = cleaned.get("salary_max")
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            self.add_error("salary_max", "Salary minimum cannot exceed maximum.")
        headcount = cleaned.get("headcount")
        if headcount is not None and headcount < 1:
            self.add_error("headcount", "Headcount must be at least 1.")
        return cleaned
