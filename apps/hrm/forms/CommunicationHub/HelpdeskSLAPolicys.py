"""HRM 3.27 Communication Hub — HelpdeskSLAPolicys forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskSLAPolicy,
)
from apps.hrm.forms.CommunicationHub._helpers import _SLA_HOUR_PAIRS


class HelpdeskSLAPolicyForm(TenantModelForm):
    class Meta:
        model = HelpdeskSLAPolicy
        fields = ["name", "description",
                  "urgent_response_hours", "urgent_resolution_hours",
                  "high_response_hours", "high_resolution_hours",
                  "medium_response_hours", "medium_resolution_hours",
                  "low_response_hours", "low_resolution_hours",
                  "is_active", "is_default"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        for resp_f, res_f, label in _SLA_HOUR_PAIRS:
            resp, res = cleaned.get(resp_f), cleaned.get(res_f)
            if resp is not None and resp < 1:
                self.add_error(resp_f, "Must be at least 1 hour.")
            if res is not None and res < 1:
                self.add_error(res_f, "Must be at least 1 hour.")
            if resp is not None and res is not None and res < resp:
                self.add_error(res_f, f"{label} resolution target cannot be shorter than its response target.")
        return cleaned
