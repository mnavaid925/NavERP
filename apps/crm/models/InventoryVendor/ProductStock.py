"""CRM 1.12 Inventory & Vendor Management — ProductStock models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ------------------------------------------------- 1.12 Inventory & Vendor Management
# CRM-owned PurchaseOrder/ProductStock (the Procurement/Inventory spine masters are not
# built yet — see "Spine-gap adaptation" in todo.md). Vendors are core.Party organizations.
class ProductStock(TenantNumbered):
    """A simple stock-tracked product (1.12) with reorder-level low-stock alerting."""

    NUMBER_PREFIX = "STK"

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True)
    on_hand_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_stk_tnt_active_idx"),
            models.Index(fields=["tenant", "name"], name="crm_stk_tnt_name_idx"),
        ]

    @property
    def is_low_stock(self):
        return self.on_hand_qty <= self.reorder_level

    def __str__(self):
        return f"{self.number} · {self.name}"
