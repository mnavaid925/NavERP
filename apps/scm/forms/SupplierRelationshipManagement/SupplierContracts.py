"""SCM 4.2 SRM — SupplierContract form."""
from django.contrib.auth import get_user_model

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _supplier_parties
from apps.scm.models import SupplierContract


class SupplierContractForm(TenantModelForm):
    class Meta:
        model = SupplierContract
        # `status` EXCLUDED — moves via refresh_status (date-driven) + the terminate/renew actions.
        # `terminated_at`/`termination_reason` are system-set.
        fields = [
            "party", "title", "contract_type", "parent_contract", "owner", "start_date", "end_date",
            "contract_value", "currency", "payment_terms", "auto_renew", "renewal_notice_days",
            "terms_summary", "document", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)
        if "parent_contract" in self.fields:
            # A contract may not be offered itself as its own master. The exclude() is inert on
            # create, where self.instance.pk is None.
            qs = SupplierContract.objects.filter(tenant=self.tenant) if self.tenant is not None \
                else SupplierContract.objects.none()
            self.fields["parent_contract"].queryset = qs.exclude(pk=self.instance.pk)
        if "owner" in self.fields and self.tenant is not None:
            # Active users PLUS whoever is already stored: scoping to is_active alone would drop a
            # deactivated owner out of the queryset, and the next unrelated edit would silently null
            # the field because a ModelChoiceField validates the submitted pk against it. `owner_id`
            # is None on create, which Django resolves to `id IS NULL` — the OR is inert there.
            #
            # The `tenant=` filter is re-applied here rather than inherited: TenantModelForm already
            # scopes User (it carries a tenant column), but assigning a fresh queryset REPLACES that
            # work, so dropping it would hand every workspace's logins to this dropdown.
            self.fields["owner"].queryset = get_user_model().objects.filter(
                Q(is_active=True) | Q(pk=self.instance.owner_id)
            ).filter(tenant=self.tenant)
        elif "owner" in self.fields:
            self.fields["owner"].queryset = get_user_model().objects.none()
        # `document` (core.Document) and `payment_terms` are tenant-scoped, so the base class scoped them.

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "The contract end date cannot be before its start.")
        return cleaned
