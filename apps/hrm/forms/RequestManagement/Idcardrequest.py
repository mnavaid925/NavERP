"""HRM 3.26 Request Management — Idcardrequest forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    IdCardRequest,
)


class IdCardRequestForm(TenantModelForm):
    """Employee's ID-card request. `card_number`/`issued_at` are stamped by the issue action; the
    reviewer/status fields are workflow-owned — none appear on the form."""

    class Meta:
        model = IdCardRequest
        fields = ["request_type", "reason_type", "reason", "delivery_location"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}
