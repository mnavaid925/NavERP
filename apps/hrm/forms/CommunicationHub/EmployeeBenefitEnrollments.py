"""HRM 3.27 Communication Hub — EmployeeBenefitEnrollments forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    BenefitPlan,
    EmployeeBenefitEnrollment,
)


class EmployeeBenefitEnrollmentForm(TenantModelForm):
    # employee is resolved server-side by _ss_child_create; status/enrolled_at/decided_by are workflow-set.
    # employee_contribution/employer_contribution are DERIVED from the plan in the view — never user-editable
    # (employer_contribution is employer money; a self-service enrollee must not be able to set it).
    class Meta:
        model = EmployeeBenefitEnrollment
        fields = ["plan", "election_choice", "coverage_tier", "effective_from", "effective_to", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "plan" in self.fields:
            self.fields["plan"].queryset = (
                BenefitPlan.objects.filter(tenant=self.tenant, is_active=True).order_by("plan_type", "name"))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("effective_from"), cleaned.get("effective_to")
        if start and end and end < start:
            self.add_error("effective_to", "Effective-to cannot be before effective-from.")
        # unique_together(tenant, employee, plan, effective_from): the form excludes tenant/employee so
        # Django can't validate it. On EDIT (instance has employee) guard against colliding with another
        # enrollment (create is guarded by the view's IntegrityError catch, where employee isn't yet known).
        if self.instance.pk and self.instance.employee_id and self.tenant is not None:
            plan, eff = cleaned.get("plan"), cleaned.get("effective_from")
            if plan and eff:
                dupe = EmployeeBenefitEnrollment.objects.filter(
                    tenant=self.tenant, employee_id=self.instance.employee_id, plan=plan, effective_from=eff
                ).exclude(pk=self.instance.pk)
                if dupe.exists():
                    self.add_error("effective_from",
                                   "This employee already has an enrollment for this plan and effective date.")
        return cleaned
