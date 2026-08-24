"""Inventory 5.15 Quality Control (QC) & Inspection — QcRoutingRuleForm."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign, _vendor_parties
from apps.inventory.models import QcRoutingRule


class QcRoutingRuleForm(TenantUniqueMixin, TenantModelForm):
    """One inspection-routing rule.

    A rule IS the receiving gate (the 5.3 approval-rule reasoning), so its writes are
    admin-gated at the view; here every tenant-scoped FK gets the crafted-POST re-check,
    the vendor dropdown is scoped to supplier/vendor-role parties, and a rule demanding
    ``inspect`` without naming its QC zone fails in model ``clean()`` keyed on
    ``qc_location_id`` — rendering as "required", not 500ing.
    """

    class Meta:
        model = QcRoutingRule
        fields = ["name", "item", "category", "vendor", "verdict",
                  "qc_location", "priority", "is_active", "notes"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if "vendor" in self.fields:
            self.fields["vendor"].queryset = _vendor_parties(tenant)
            self.fields["vendor"].required = False

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "category", "vendor", "qc_location"])
        return cleaned
