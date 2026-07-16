"""HRM 3.27 Communication Hub — Assets forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Asset,
)


class AssetForm(TenantModelForm):
    """Central asset register. `current_holder` is excluded — it is system-managed by
    AssetAllocation._sync_linked_asset() via the assign/return actions, never hand-edited. `status`
    stays editable so HR can hand-correct it (an out-of-band edit here does NOT create an allocation)."""

    class Meta:
        model = Asset
        fields = ["asset_tag", "name", "category", "manufacturer", "model_number", "serial_number",
                  "status", "condition", "purchase_date", "purchase_cost", "currency", "warranty_expiry",
                  "location", "depreciation_method", "useful_life_months", "salvage_value", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        cost, salvage = cleaned.get("purchase_cost"), cleaned.get("salvage_value")
        if cost is not None and salvage is not None and salvage > cost:
            self.add_error("salvage_value", "Salvage value cannot exceed purchase cost.")
        method = cleaned.get("depreciation_method")
        if method and method != "none" and not cleaned.get("useful_life_months"):
            self.add_error("useful_life_months",
                           "Useful life (months) is required for this depreciation method.")
        # Don't let a hand-edit set the asset back to in_stock while an issued allocation is still
        # open (that would desync current_holder + allow a double-issue) — return it properly first.
        if self.instance.pk and cleaned.get("status") == "in_stock":
            if self.instance.allocations.filter(status="issued").exists():
                self.add_error("status", "Return the active allocation before setting this asset "
                                         "back to in-stock.")
        return cleaned
