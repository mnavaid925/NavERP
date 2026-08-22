"""Inventory 5.3 Purchase Order (PO) Management — PurchaseOrderApprovalRule form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin
from apps.inventory.models import PurchaseOrderApprovalRule


class PurchaseOrderApprovalRuleForm(TenantUniqueMixin, TenantModelForm):
    """One value-band routing policy. ``name`` is tenant-unique via TenantUniqueMixin;
    the band sanity check lives on the model so the admin obeys it too."""

    class Meta:
        model = PurchaseOrderApprovalRule
        fields = ["name", "min_amount", "max_amount", "org_unit", "tier_count", "is_active"]
