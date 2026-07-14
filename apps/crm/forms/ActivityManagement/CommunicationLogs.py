"""CRM 1.5 Activity & Communication Management — CommunicationLogs forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    CommunicationLog,
)


class CommunicationLogForm(TenantModelForm):
    class Meta:
        model = CommunicationLog
        # number is system-set; email_message_id is populated by the sync engine, not staff.
        fields = ["channel", "direction", "subject", "body", "party", "owner",
                  "related_opportunity", "related_case", "occurred_at", "duration_seconds",
                  "outcome", "logged_via"]
