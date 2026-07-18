"""SCM 4.4 Warehouse Management — PutawayTask.

The inbound half of WMS: once a goods receipt lands stock in a staging location, a putaway task
directs it to its final bin. Completing the task posts the staging→bin movement through the SAME
4.3 posting service everything else uses — it never writes StockMove itself and never stores a
quantity, so on-hand stays a pure aggregate of the append-only ledger.

Item resolution note: `GoodsReceiptLine`/`PurchaseOrderLine` are still free-text (`item_description`/
`sku_hint`) because they predate the 4.3 item master, so a putaway task carries its OWN `item` FK
that a user picks (optionally matched from the receipt's `sku_hint`). Backfilling those 4.1 lines
onto `scm.Item` is a documented follow-up, not something to fake here.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class PutawayTask(TenantNumbered):
    """Directs received stock from a staging location to its final bin [PUT-]."""

    NUMBER_PREFIX = "PUT"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("pending", "in_progress")
    # Statuses a putaway can still be actioned from.
    OPEN_STATUSES = ("pending", "in_progress")

    STRATEGY_CHOICES = [
        ("directed", "Directed"),      # system suggests the bin
        ("fixed", "Fixed Location"),   # the item has a home bin
        ("random", "Random"),          # any free bin
        ("cross_dock", "Cross-Dock"),  # straight to outbound, skip storage
    ]

    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="putaway_tasks",
                                      help_text="The receipt these goods arrived on")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="putaway_tasks")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="putaway_tasks")
    from_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                      related_name="putaways_out",
                                      help_text="Staging / receiving location holding the stock")
    to_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                    related_name="putaways_in", help_text="Destination bin")
    quantity = models.DecimalField(max_digits=16, decimal_places=4,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    strategy = models.CharField(max_length=12, choices=STRATEGY_CHOICES, default="directed")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="scm_putaway_tasks")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_put_tnt_status_idx"),
            models.Index(fields=["tenant", "to_location"], name="scm_put_tnt_toloc_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    def clean(self):
        super().clean()
        if self.from_location_id and self.from_location_id == self.to_location_id:
            raise ValidationError("Putaway source and destination must be different locations.")

    def __str__(self):
        to_code = self.to_location.code if self.to_location_id else "?"
        return f"{self.number or 'PUT'} · {self.item_id and self.item.sku} → {to_code}"
