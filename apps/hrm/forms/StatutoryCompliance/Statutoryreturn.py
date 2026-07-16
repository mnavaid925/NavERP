"""HRM 3.15 Statutory Compliance — Statutoryreturn forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    PayrollCycle,
    StatutoryReturn,
)


class StatutoryReturnForm(TenantModelForm):
    # number + all derived totals + the filing/payment workflow fields are set by the model /
    # generate / mark_* actions — this form only carries the return's metadata.
    class Meta:
        model = StatutoryReturn
        fields = ["scheme", "period_type", "period_start", "period_end", "cycle", "employee",
                  "due_date", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "cycle" in self.fields:
                self.fields["cycle"].queryset = (
                    PayrollCycle.objects.filter(tenant=self.tenant).order_by("-pay_date"))
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))

    def clean(self):
        # One return per (tenant, scheme, period_start, employee). Enforced here at the FORM level
        # (not model.clean) because tenant is excluded from the form and only set in the view AFTER
        # validation — so a model.clean() guard couldn't see it on create; self.tenant always can.
        # This closes the org-level (employee=None) duplicate hole that unique_together leaves open,
        # since MariaDB treats NULL as distinct in a unique index (mirrors the StatutoryStateRule LWF
        # NULL-uniqueness concern).
        cleaned = super().clean()
        scheme = cleaned.get("scheme")
        period_start = cleaned.get("period_start")
        employee = cleaned.get("employee")
        if self.tenant is not None and scheme and period_start:
            dupe = StatutoryReturn.objects.filter(
                tenant=self.tenant, scheme=scheme, period_start=period_start, employee=employee)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                raise forms.ValidationError(
                    "A statutory return for this scheme, period start and employee already exists.")
        return cleaned
