"""Inventory 5.6 Inventory Tracking & Control — StockStatus.

**Stock Status Management** bullet: categorizing stock as Active, Damaged, Expired or
On-Hold. The append-only ``scm.StockMove`` ledger (L36/L29) records HOW MUCH stock sits
where but carries no classification dimension — nothing in the spine can say "ten of
the fifty units in BIN-01 are damaged". This is that missing layer: a SOFT CLAIM about
a slice of the on-hand at one spot, exactly the ``scm.SalesOrderAllocation`` precedent
(L37) — it posts NO StockMove, so the ledger stays the single source of physical truth.

What the claim buys: the Real-Time Stock Levels page subtracts every non-active
classification from availability, so damaged/expired/on-hold stock stops promising
itself to orders. Unclassified stock is sellable by default — a workspace that never
touches this table behaves exactly as it did before it existed.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class StockStatus(TenantOwned):
    """One classification of a quantity of stock sitting at one location [of 5.6]."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("damaged", "Damaged"),
        ("expired", "Expired"),
        ("on_hold", "On Hold"),
    ]
    #: Statuses under which the classified quantity may still promise itself to orders.
    SELLABLE_STATUSES = ("active",)

    #: Badge colour per status, decided in ONE place. theme.css ships colour-named badge
    #: modifiers only (green/red/amber/info/muted/slate) — the semantic -success/-warning/
    #: -danger variants do not exist and render unstyled (lesson L33).
    STATUS_CSS = {
        "active": "badge-green",
        "damaged": "badge-red",
        "expired": "badge-amber",
        "on_hold": "badge-info",
    }

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, related_name="stock_statuses",
        help_text="The item whose stock is being classified")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="stock_statuses",
        help_text="Where the classified units sit")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_statuses",
        help_text="Optional lot/serial — expiry usually belongs to a specific batch")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="damaged")
    quantity = models.DecimalField(
        max_digits=16, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="How many of the units at this spot the claim covers")
    reason = models.CharField(
        max_length=255, blank=True,
        help_text="Why the units carry this status, e.g. 'fork puncture case 3'")
    effective_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the classification was observed")

    class Meta:
        ordering = ["item__sku", "location__code", "-effective_at"]
        indexes = [models.Index(fields=["tenant", "status"], name="inv_ss_tnt_status_idx")]

    # -- state ---------------------------------------------------------------------------------

    @property
    def is_sellable(self):
        return self.status in self.SELLABLE_STATUSES

    @property
    def status_css(self):
        """The badge class for this row's status — see :attr:`STATUS_CSS`."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    def spot_moves(self):
        """The ledger queryset this claim draws from: the item's moves at its location,
        narrowed to the named lot when there is one.

        The ``tenant`` predicate is not optional scoping — item and location are already
        same-tenant by clean() — it is what lets MariaDB drive
        ``scm_move_tnt_item_loc_idx`` from its (tenant, item, location) prefix instead of
        scanning the item's whole move history across every location.
        """
        qs = self.item.stock_moves.filter(tenant=self.tenant_id, location=self.location)
        if self.lot_serial_id is not None:
            qs = qs.filter(lot_serial=self.lot_serial)
        return qs

    def spot_on_hand(self):
        """Live ledger total at this spot — the ceiling every classification shares."""
        total = self.spot_moves().aggregate(q=Sum("quantity"))["q"]
        return total or ZERO

    def clean(self):
        super().clean()
        if self.location_id and self.location.tenant_id != self.tenant_id:
            raise ValidationError({"location": "That location belongs to another workspace."})
        if self.lot_serial_id:
            if self.lot_serial.tenant_id != self.tenant_id:
                raise ValidationError({"lot_serial": "That lot/serial belongs to another workspace."})
            if self.item_id and self.lot_serial.item_id != self.item_id:
                raise ValidationError({"lot_serial": "That lot/serial belongs to a different item."})

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        where = self.location.code if self.location_id else "?"
        return f"{sku} @ {where} · {self.get_status_display()} ×{self.quantity}"
