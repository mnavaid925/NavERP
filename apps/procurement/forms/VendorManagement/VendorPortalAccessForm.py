"""Procurement 6.4 Vendor Management — forms."""
from django import forms

from apps.procurement.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.procurement.models import VendorPortalAccess


class VendorPortalAccessForm(TenantUniqueMixin, TenantModelForm):
    """One vendor-portal login binding (staff-managed console row)."""

    class Meta:
        model = VendorPortalAccess
        fields = ["supplier", "portal_user", "is_active", "note"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["supplier"])
        # portal_user carries its own tenant column but is not a scoped ModelChoiceField,
        # so _reject_foreign's list does not cover it — guard it manually.
        chosen = cleaned.get("portal_user")
        if chosen and chosen.tenant_id != (self.tenant.pk if self.tenant else None):
            self.add_error("portal_user", "That record belongs to another workspace.")
        return cleaned
