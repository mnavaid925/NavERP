"""SCM 4.3 Inventory Management — StockTransfer + StockTransferLine.

Moves stock between two Locations. Completing a transfer posts a PAIRED StockMove per line — a
negative move out of the source and a positive move into the destination — inside one atomic block,
so the two legs can never disagree. The posting itself lives in the views StockMove service; the model
holds the document and its state machine.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class StockTransfer(TenantNumbered):
    """A stock transfer between locations [TRF-]."""

    NUMBER_PREFIX = "TRF"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_transit", "In Transit"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft",)

    from_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                      related_name="transfers_out")
    to_location = models.ForeignKey("scm.Location", on_delete=models.PROTECT,
                                    related_name="transfers_in")
    transfer_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-transfer_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="scm_trf_tnt_status_idx")]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def clean(self):
        super().clean()
        if self.from_location_id and self.from_location_id == self.to_location_id:
            raise ValidationError("A transfer's source and destination must be different locations.")

    def __str__(self):
        # NOTE (bug fix): this used to interpolate from_location_id/to_location_id — the raw numeric
        # FK ids — instead of the locations' human-readable codes. Every sibling __str__ in this
        # module (Location, StockMove, ...) renders a code, not a pk; a transfer's own string should
        # say "WH1 → WH2", not "3 → 7". Not used by any template/admin list today (grepped), so this
        # is a safe fix rather than a behaviour change anything depends on.
        from_code = self.from_location.code if self.from_location_id else "?"
        to_code = self.to_location.code if self.to_location_id else "?"
        return f"{self.number or 'TRF'} · {from_code} → {to_code}"


class StockTransferLine(models.Model):
    """One item moved on a transfer. ``lot_serial`` optional (only for tracked items)."""

    transfer = models.ForeignKey("scm.StockTransfer", on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="transfer_lines")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="transfer_lines")
    quantity = models.DecimalField(max_digits=16, decimal_places=4,
                                   validators=[MinValueValidator(Decimal("0.0001"))])

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.item_id and self.item.sku} ×{self.quantity}"
