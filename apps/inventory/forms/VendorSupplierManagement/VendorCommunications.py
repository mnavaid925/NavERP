"""Inventory 5.2 Vendor / Supplier Management — VendorCommunication form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign, _vendor_parties
from apps.inventory.models import VendorCommunication


class VendorCommunicationForm(TenantUniqueMixin, TenantModelForm):
    """One logged vendor interaction. ``number`` is auto-assigned in ``save()`` and the
    provenance of who logged it lives in core.AuditLog, so neither is a form field."""

    class Meta:
        model = VendorCommunication
        fields = ["party", "channel", "direction", "subject", "body",
                  "occurred_at", "follow_up_on"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Narrow the vendor dropdown to parties actually carrying a supplier/vendor role —
        # TenantModelForm's blanket tenant scoping would list customers and carriers too.
        self.fields["party"].queryset = _vendor_parties(self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["party"])
        return cleaned
