"""CRM 1.12 Inventory & Vendor Management — ProductStock forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    ProductStock,
)


class ProductStockForm(TenantModelForm):
    class Meta:
        model = ProductStock
        # WARNING: on_hand_qty is system-managed via PO receipt (crm_po_receive) — excluded so
        # members can't directly rewrite inventory counts that the partner portal exposes.
        fields = ["name", "sku", "reorder_level", "unit_cost", "is_active", "description"]
