"""Accounting 2.6 Fixed Assets — AssetDisposals forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    AssetDisposal,
    FixedAsset,
)


class AssetDisposalForm(TenantModelForm):
    class Meta:
        model = AssetDisposal
        fields = ["asset", "disposal_date", "proceeds", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant, status="active")
