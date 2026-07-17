"""SCM 4.2 SRM — SupplierContract form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _supplier_parties
from apps.scm.models import SupplierContract


class SupplierContractForm(TenantModelForm):
    class Meta:
        model = SupplierContract
        # `status` EXCLUDED — moves via refresh_status (date-driven) + the terminate/renew actions.
        # `terminated_at`/`termination_reason` are system-set.
        fields = [
            "party", "title", "contract_type", "start_date", "end_date", "contract_value",
            "currency", "payment_terms", "auto_renew", "renewal_notice_days", "terms_summary",
            "document", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)
        # `document` (core.Document) and `payment_terms` are tenant-scoped, so the base class scoped them.

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "The contract end date cannot be before its start.")
        return cleaned
