"""CRM 1.12 Inventory & Vendor Management — PurchaseOrders forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    PurchaseOrder,
    PurchaseOrderLine,
)


class PurchaseOrderForm(TenantModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["vendor", "status", "order_date", "expected_date", "notes", "owner"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Vendors are organization Parties.
        if self.tenant is not None:
            self.fields["vendor"].queryset = Party.objects.filter(
                tenant=self.tenant, kind="organization").order_by("name")


class PurchaseOrderLineForm(TenantModelForm):
    """Inline on the PurchaseOrder form/detail; tenant/purchase_order set in the view."""

    class Meta:
        model = PurchaseOrderLine
        fields = ["item_name", "product", "quantity", "unit_price"]  # order auto-assigned in the view
