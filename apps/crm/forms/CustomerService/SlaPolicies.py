"""CRM 1.4 Customer Service & Support — SlaPolicies forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    SlaPolicy,
)


# ===== 1.4 Customer Service & Support (recreated) ===========================
class SlaPolicyForm(TenantModelForm):
    class Meta:
        model = SlaPolicy
        fields = ["name", "description", "is_active", "is_default",
                  "response_low", "response_medium", "response_high", "response_critical",
                  "resolution_low", "resolution_medium", "resolution_high", "resolution_critical"]
