"""CRM 1.8 Project & Delivery Management — Projects forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmProject,
)


class CrmProjectForm(TenantModelForm):
    class Meta:
        model = CrmProject
        fields = ["name", "account", "source_opportunity", "status", "start_date",
                  "end_date", "budget", "owner", "description"]
