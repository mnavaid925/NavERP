"""Procurement 6.12 Goods Receipt & Inspection — ReceiptTolerancePolicyForm.

A rule master changes what the WHOLE workspace flags, so its writes are admin-gated at the view
(the 5.15 ``QcRoutingRule`` / 6.3 ``ApprovalRoutingRule`` precedent). Here the job is narrower and
just as load-bearing: every tenant-scoped FK dropdown is narrowed to this workspace AND re-checked
after the POST, because a narrowed ``<select>`` is UX, not an authorization boundary.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import ReceiptTolerancePolicy


def _supplier_parties(tenant):
    """Parties this workspace can buy from — a LOCAL mirror of the helper 6.10 already keeps in
    ``forms/PurchaseOrderManagement/PurchaseOrderChanges.py`` (peer sub-modules copy it rather
    than import each other's private names). ``core.PartyRole`` distinguishes ``supplier`` from
    ``vendor``; BOTH are accepted so the dropdown never hides half the counterparties."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


class ReceiptTolerancePolicyForm(TenantUniqueMixin, TenantModelForm):
    """One over/under/early/late receipt tolerance band.

    ``TenantUniqueMixin`` is mixed in FIRST on purpose: the model's ``clean()`` compares every
    chosen FK's tenant against ``self.tenant_id``, and the CRUD helpers only assign the real
    tenant AFTER ``is_valid()``. Without the mixin's early stamp, every CREATE would be falsely
    rejected as cross-tenant.
    """

    class Meta:
        model = ReceiptTolerancePolicy
        # EXCLUDED and why: ``tenant`` is stamped by the create view (and by TenantUniqueMixin
        # before validation); ``created_at``/``updated_at`` are system timestamps. Nothing else —
        # this is a CONFIGURATION MASTER, not a workflow document, so there is no status, no
        # number and no verb stamps to protect from the form.
        fields = ["name", "item", "category", "vendor",
                  "over_receipt_pct", "under_receipt_pct", "over_receipt_qty",
                  "allow_unlimited_over_receipt", "early_receipt_days", "late_receipt_days",
                  "action", "price_variance_pct", "priority", "is_active", "notes"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # TenantModelForm already scopes FKs whose TARGET model carries a tenant column, but the
        # ordering (and the vendor role narrowing, which it cannot know about) is ours.
        from apps.scm.models import Item, ItemCategory

        if "item" in self.fields:
            self.fields["item"].queryset = (
                Item.objects.filter(tenant=tenant).order_by("sku") if tenant is not None
                else Item.objects.none())
            self.fields["item"].required = False
        if "category" in self.fields:
            self.fields["category"].queryset = (
                ItemCategory.objects.filter(tenant=tenant).order_by("name") if tenant is not None
                else ItemCategory.objects.none())
            self.fields["category"].required = False
        if "vendor" in self.fields:
            self.fields["vendor"].queryset = _supplier_parties(tenant)
            self.fields["vendor"].required = False

    def clean(self):
        cleaned = super().clean()
        # The crafted-POST re-check. A hand-edited POST can carry any pk; the narrowed dropdown
        # above never sees it.
        _reject_foreign(self, cleaned, ["item", "category", "vendor"])
        return cleaned

    # No DateFields on this form at all — and even if one were added, TenantModelForm already
    # owns date widgets (DateInput type="date" + input_formats). Never re-declare them here (L22).
