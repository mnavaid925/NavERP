"""HRM 3.5 Job Requisition — RequisitionApprovals forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    RequisitionApproval,
)


class RequisitionApprovalForm(TenantModelForm):
    # SECURITY: `status`, `decided_at`, `decided_by` are excluded — set only by the approve/reject/
    # return actions. `requisition` is set in the view (the step is added from the requisition hub).
    class Meta:
        model = RequisitionApproval
        fields = ["step_order", "approver", "approver_role", "comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Approvers are tenant users (an approval step authorizes a hire for this workspace).
        if self.tenant is not None:
            self.fields["approver"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True)
                .order_by("username"))
        else:
            self.fields["approver"].queryset = get_user_model().objects.none()
