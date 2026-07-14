"""CRM 1.8 Project & Delivery Management — ResourceAllocation forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    ResourceAllocation,
)


class ResourceAllocationForm(TenantModelForm):
    """1.8 Resource Allocation — a planned capacity booking. ``project``/``assignee`` dropdowns are
    auto-scoped to the tenant by the base form."""

    class Meta:
        model = ResourceAllocation
        fields = ["project", "assignee", "role", "hours_per_week", "start_date",
                  "end_date", "status", "notes"]

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("End date must be on or after the start date.")
        return cleaned
