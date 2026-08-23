"""Inventory 5.7 Stock Movement & Transfers — TransferApprovalRule form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin
from apps.inventory.models import TransferApprovalRule


class TransferApprovalRuleForm(TenantUniqueMixin, TenantModelForm):
    """One approval-routing policy. No tenant-scoped FK to re-check — scope, unit band
    and tier count are all plain fields; the cross-field band check lives on the model."""

    class Meta:
        model = TransferApprovalRule
        fields = ["name", "applies_to", "min_units", "max_units", "tier_count", "is_active"]
