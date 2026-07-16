"""HRM 3.21 Performance Improvement — WarningAcknowledges forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    WarningLetter,
)


class WarningAcknowledgeForm(TenantModelForm):
    # Captures the recipient's optional written response at acknowledgment time (the ONLY employee_response
    # write path). tenant= kept for signature parity.
    class Meta:
        model = WarningLetter
        fields = ["employee_response"]
        widgets = {
            "employee_response": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }
