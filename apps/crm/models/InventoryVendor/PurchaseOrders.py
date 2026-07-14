"""CRM 1.12 Inventory & Vendor Management — PurchaseOrders models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class PurchaseOrder(TenantNumbered):
    """A CRM-owned purchase order to a vendor (1.12). ``total_amount`` is recomputed from lines."""

    NUMBER_PREFIX = "PO"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]

    vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_purchase_orders")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    order_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # recomputed from lines
    received_at = models.DateTimeField(null=True, blank=True)  # system-set on receive
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_purchase_orders")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_po_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_po_tnt_created_idx"),
        ]

    def recalc_total(self):
        """Sum line totals into ``total_amount`` (call after line add/edit/delete)."""
        agg = self.lines.aggregate(
            t=models.Sum(models.F("quantity") * models.F("unit_price"),
                         output_field=models.DecimalField(max_digits=18, decimal_places=2)))
        self.total_amount = agg["t"] or Decimal("0")
        self.save(update_fields=["total_amount", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.vendor or 'Vendor'}"


class PurchaseOrderLine(models.Model):
    """A line item on a CRM PurchaseOrder (1.12). ``line_total`` is derived."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    purchase_order = models.ForeignKey("crm.PurchaseOrder", on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("crm.ProductStock", on_delete=models.SET_NULL, null=True, blank=True, related_name="po_lines")
    item_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    @property
    def line_total(self):
        return Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)

    def __str__(self):
        return f"{self.item_name} ×{self.quantity}"
