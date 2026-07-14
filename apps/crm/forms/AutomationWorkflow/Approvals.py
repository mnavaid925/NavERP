"""CRM 1.10 Automation & Workflow Engine — Approvals forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    ApprovalRequest,
)


class ApprovalRequestForm(TenantModelForm):
    class Meta:
        model = ApprovalRequest
        fields = ["rule", "subject", "record_label", "approver", "requested_by",
                  "threshold_field", "threshold_value"]
