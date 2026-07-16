"""HRM 3.27 Communication Hub — AssetMaintenances forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    AssetMaintenance,
)


class AssetMaintenanceForm(TenantModelForm):
    class Meta:
        model = AssetMaintenance
        fields = ["asset", "maintenance_type", "status", "scheduled_date", "completed_date", "vendor",
                  "cost", "contract_start", "contract_end", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        sched, comp = cleaned.get("scheduled_date"), cleaned.get("completed_date")
        if sched and comp and comp < sched:
            self.add_error("completed_date", "Completed date cannot be before the scheduled date.")
        cs, ce = cleaned.get("contract_start"), cleaned.get("contract_end")
        if cs and ce and ce <= cs:
            self.add_error("contract_end", "Contract end date must be after the contract start date.")
        return cleaned
