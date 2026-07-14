"""CRM 1.1 Core Data Management — Leads forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Lead,
)


class LeadForm(TenantModelForm):
    class Meta:
        model = Lead
        fields = ["name", "company", "title", "email", "phone", "source", "rating",
                  "status", "score", "est_value", "owner", "description"]
