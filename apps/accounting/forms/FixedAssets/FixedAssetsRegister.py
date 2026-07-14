"""Accounting 2.6 Fixed Assets — FixedAssetsRegister forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    FixedAsset,
)


class FixedAssetForm(TenantModelForm):
    class Meta:
        model = FixedAsset
        fields = ["name", "category", "acquisition_cost", "salvage_value", "useful_life_months",
                  "method", "in_service_date", "status", "asset_account", "accumulated_account",
                  "expense_account", "custodian", "location", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'disposed' is reached only via the AssetDisposal posting action, never by hand.
        self.fields["status"].choices = [c for c in FixedAsset.STATUS_CHOICES if c[0] != "disposed"]
