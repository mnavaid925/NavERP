"""HRM 3.2 Organizational Structure — LeaveRequests forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveRequest,
)


class LeaveRequestForm(TenantModelForm):
    # SECURITY: `status` and `approver` are deliberately NOT form fields — a new request starts
    # as the model default "draft", and both are set only by the privileged workflow actions
    # (submit/approve/reject). Exposing them here would let any user self-approve via a crafted POST.
    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "reason"]
