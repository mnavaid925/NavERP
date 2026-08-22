"""Inventory 5.3 Purchase Order (PO) Management — PurchaseOrderDispatch form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import PurchaseOrderDispatch
from apps.scm.models import PurchaseOrder


class PurchaseOrderDispatchForm(TenantUniqueMixin, TenantModelForm):
    """Record one transmission of a purchase order.

    The order dropdown only offers orders a dispatch can honestly exist for: APPROVED and
    beyond, not yet closed (cancelled/closed orders are terminal — re-sending them would
    lie). The channel/recipient rule is enforced on the MODEL so the admin and any future
    writer obey it too; here it just renders as a field error via clean().

    TenantUniqueMixin stays even though this model has no tenant-unique constraint: its
    ``clean()`` compares the chosen order's tenant against ``self.tenant_id``, which on
    CREATE is only stamped if the mixin did it (the ProductFile SEC-1 lesson).
    """

    class Meta:
        model = PurchaseOrderDispatch
        fields = ["purchase_order", "channel", "recipient", "reference", "dispatched_at", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].queryset = _dispatchable_orders(self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["purchase_order"])
        return cleaned


def _dispatchable_orders(tenant):
    """Orders this workspace may still transmit: approved and past it, never closed."""
    if tenant is None:
        return PurchaseOrder.objects.none()
    closed = list(PurchaseOrder.CLOSED_STATUSES) + ["draft", "pending_approval"]
    return (PurchaseOrder.objects.filter(tenant=tenant)
            .exclude(status__in=closed)
            .select_related("vendor")
            .order_by("-order_date", "-id"))
