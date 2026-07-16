"""HRM 3.4 Employee Offboarding — Clearanceitem forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    AssetAllocation,
    ClearanceItem,
)


class ClearanceItemForm(TenantModelForm):
    # SECURITY: `status`, `cleared_by`, `cleared_at` are excluded — set only by the mark-cleared /
    # mark-na / reject workflow actions (the mark-cleared action also returns the linked asset).
    class Meta:
        model = ClearanceItem
        fields = ["case", "department", "department_label", "description", "is_mandatory",
                  "assigned_to", "due_date", "asset_allocation", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only an issued asset can be the subject of a return-clearance line.
        if self.tenant is not None:
            self.fields["asset_allocation"].queryset = (
                AssetAllocation.objects.filter(tenant=self.tenant, status="issued")
                .select_related("employee__party").order_by("-issued_at"))
