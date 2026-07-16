"""HRM 3.2 Organizational Structure — LeaveEncashments forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveEncashment,
)


class LeaveEncashmentForm(TenantModelForm):
    # `amount` is derived (days × rate) and status/approver/approved_at/paid_on/payment_reference/
    # decision_note are workflow-set in the view — never on the form (no self-approve via crafted POST).
    class Meta:
        model = LeaveEncashment
        fields = ["employee", "leave_type", "year", "days", "rate_per_day"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only encashable leave types can be encashed — narrow the dropdown to match the model clean().
        if "leave_type" in self.fields:
            self.fields["leave_type"].queryset = self.fields["leave_type"].queryset.filter(encashable=True)
