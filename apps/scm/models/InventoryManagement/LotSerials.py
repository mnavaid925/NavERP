"""SCM 4.3 Inventory Management — LotSerial (batch / serial tracking)."""
from apps.scm.models._base import *  # noqa: F401,F403


class LotSerial(TenantOwned):
    """A tracked lot/batch or an individual serial number for a lot/serial-tracked item."""

    KIND_CHOICES = [("lot", "Lot / Batch"), ("serial", "Serial")]
    STATUS_CHOICES = [
        ("available", "Available"),
        ("quarantine", "Quarantine"),
        ("expired", "Expired"),
        ("consumed", "Consumed"),
    ]

    item = models.ForeignKey("scm.Item", on_delete=models.CASCADE, related_name="lot_serials")
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, default="lot")
    number = models.CharField(max_length=64, help_text="Lot/batch code or serial number")
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="available")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku", "number"]
        unique_together = ("tenant", "item", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="scm_lot_tnt_status_idx")]

    def on_hand(self):
        return self.stock_moves.aggregate(q=Sum("quantity"))["q"] or ZERO

    def __str__(self):
        return f"{self.item_id and self.item.sku}·{self.number}"
