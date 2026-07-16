"""HRM 3.3 Employee Onboarding — Assetallocation forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    AssetAllocation,
)


class AssetAllocationForm(TenantModelForm):
    # `issued_at` / `issued_by` are stamped by the Issue action (and `returned_at` by Return) — kept
    # out of the form so they can't be hand-spoofed/back-dated. `status` stays editable so HR can
    # record lost/damaged; the Issue/Return actions own the issued↔returned transition + timestamps.
    class Meta:
        model = AssetAllocation
        # `asset` (optional) links this issuance to a specific 3.33 register row — when set, saving
        # this form syncs Asset.status/current_holder via AssetAllocation._sync_linked_asset().
        fields = ["program", "employee", "asset", "asset_name", "asset_category", "serial_number",
                  "asset_tag", "status", "return_due_date", "notes"]

    def clean(self):
        cleaned = super().clean()
        asset, status = cleaned.get("asset"), cleaned.get("status")
        # Don't let an "issued" allocation link an asset that already has another active (issued)
        # allocation — that would double-issue one register asset (bypassing the asset_assign guard).
        if asset and status == "issued":
            clash = asset.allocations.filter(status="issued").exclude(pk=self.instance.pk).exists()
            if clash:
                self.add_error("asset", "This asset already has an active (issued) allocation. "
                                        "Return it before re-issuing.")
        return cleaned
