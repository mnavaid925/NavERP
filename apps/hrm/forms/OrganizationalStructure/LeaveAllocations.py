"""HRM 3.2 Organizational Structure — LeaveAllocations forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveAllocation,
)


class LeaveAllocationForm(TenantModelForm):
    class Meta:
        model = LeaveAllocation
        fields = ["employee", "leave_type", "year", "allocated_days", "note", "status"]

    def save(self, commit=True):
        obj = super().save(commit=False)
        # A manual edit to allocated_days resets the carry-forward baseline — otherwise the engine's
        # idempotency invariant (allocated = accrued/base + carried_forward) is left inconsistent and
        # the next carry-forward run would mis-account the hand-edited value.
        if "allocated_days" in self.changed_data:
            obj.carried_forward = 0
        if commit:
            obj.save()
            self.save_m2m()
        return obj
