"""HRM 3.26 Request Management — Documentrequest forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    DocumentRequest,
)


class DocumentRequestForm(TenantModelForm):
    """Employee's official-letter request. Workflow fields (status/approver/approved_at/
    decision_note/fulfilled_at/output_file) are set by the approve/fulfill actions, and `employee`
    is resolved server-side by _ss_child_create — none appear on the form."""

    class Meta:
        model = DocumentRequest
        fields = ["document_type", "purpose", "addressed_to", "copies", "delivery_method", "needed_by"]
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3})}
