"""SCM 4.3 Inventory Management — StockMove, the append-only stock ledger.

Every change in stock is a StockMove row with a SIGNED quantity (+ into a location, − out of it).
On-hand for any (item, location, lot) is the SUM of its moves — there is no stored quantity anywhere,
so nothing can drift from the ledger. A StockMove is NEVER edited or deleted (no form, no admin write,
no delete view): a mistake is corrected by posting a compensating move, exactly like the accounting
JournalEntry reversal pattern. ``unit_cost`` on each inbound move IS the FIFO/LIFO/WAC cost layer the
valuation report walks — no separate cost-layer table is needed.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class StockMove(TenantOwned):
    """One append-only movement of stock. Signed quantity; created only via the posting service."""

    MOVE_TYPES = [
        ("receipt", "Receipt"),        # inbound (GRN, opening balance)
        ("issue", "Issue"),            # outbound (consumption, shipment)
        ("transfer", "Transfer"),      # between locations (posted as a −/+ pair)
        ("adjustment", "Adjustment"),  # write-off / damage / cycle count / found / revaluation
    ]

    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="stock_moves")
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, related_name="stock_moves")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="stock_moves")
    # Signed: positive = into the location, negative = out of it.
    quantity = models.DecimalField(max_digits=16, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                    validators=[MinValueValidator(ZERO)])
    move_type = models.CharField(max_length=12, choices=MOVE_TYPES)
    reference = models.CharField(max_length=40, blank=True,
                                 help_text="Source document number, e.g. TRF-00001 / ADJ-00001 / GRN-00001")
    reason = models.CharField(max_length=120, blank=True)
    moved_at = models.DateTimeField()

    class Meta:
        ordering = ["-moved_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "item", "location"], name="scm_move_tnt_item_loc_idx"),
            # Mirror index: the ledger is queried by BOTH dimensions (per-item pages and per-location
            # pages). A (tenant, location) filter can't use the index above — location isn't a prefix.
            models.Index(fields=["tenant", "location", "item"], name="scm_move_tnt_loc_item_idx"),
            models.Index(fields=["tenant", "moved_at"], name="scm_move_tnt_movedat_idx"),
            models.Index(fields=["tenant", "reference"], name="scm_move_tnt_ref_idx"),
        ]

    @property
    def value(self):
        return (self.quantity or ZERO) * (self.unit_cost or ZERO)

    def __str__(self):
        sign = "+" if (self.quantity or ZERO) >= ZERO else ""
        return f"{sign}{self.quantity} {self.item_id and self.item.sku} @ {self.location_id and self.location.code}"
