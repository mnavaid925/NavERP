"""Inventory 5.5 Warehousing & Bin Management — CrossDockOrder.

**Cross-Docking** bullet: goods flow from the receiving dock straight to dispatch,
never touching a storage bin. The bypass is an OPERATIONAL DECISION about flow, not a
new kind of stock — so the document lives here while its two ledger legs post into
SCM 4.3's append-only ``StockMove`` book exactly like every other movement (L36/L29):
a ``receipt`` when the trailer is unloaded at the dock and an ``issue`` when it leaves.
On-hand, valuation and 4.7's demand series all stay pure aggregates of that one ledger;
nothing here stores a quantity of its own.

The lifecycle mirrors what the dock actually does::

    draft ──receive()──▶ received ──ship()──▶ shipped
      │                     │
      └────────cancel()─────┘   (received: posts a GUARDED compensating −receipt,
                                 the JournalEntry-reversal pattern — never a delete)

Every action re-reads its row FOR UPDATE inside the atomic block before guarding, so a
double-clicked button cannot post the receipt twice; and every action writes its audit
row INSIDE the transaction, so a committed move always has its trail.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403


def _shortfall(item, location, quantity, lot_serial=None):
    """Message when ``location`` can't cover an outbound ``quantity``, else ''.

    Same rule as scm's posting service (kept local: used by this entity only): scoped
    to (item, location) AND the named lot when there is one — checking a lot's
    tenant-wide total instead would let a cross-dock ship stock the dock never held.
    Reads the live aggregate, so moves posted earlier in the same transaction count.
    """
    qs = item.stock_moves.filter(location=location)
    if lot_serial is not None:
        qs = qs.filter(lot_serial=lot_serial)
    available = qs.aggregate(q=Sum("quantity"))["q"] or ZERO
    if quantity > available:
        return (f"{item.sku}: only {available} available at {location.code}, "
                f"cannot ship {quantity}.")
    return ""


class CrossDockOrder(TenantNumbered):
    """One bypass-storage flow [XD-] from receiving dock to dispatch."""

    NUMBER_PREFIX = "XD"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("received", "Received at Dock"),
        ("shipped", "Shipped"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft",)
    #: Statuses cancel() accepts — once shipped, only a compensating document undoes it.
    CANCELLABLE_STATUSES = ("draft", "received")

    #: Badge colour per status, decided in ONE place. theme.css ships colour-named badge
    #: modifiers only (green/red/amber/info/muted/slate) — the semantic -success/-warning/
    #: -danger variants do not exist and render unstyled (lesson L33).
    STATUS_CSS = {
        "draft": "badge-slate",
        "received": "badge-info",
        "shipped": "badge-green",
        "cancelled": "badge-red",
    }

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, related_name="crossdock_orders",
        help_text="The product flowing dock-to-dock")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="crossdock_orders",
        help_text="Optional lot/serial for tracked items")
    dock_location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="crossdock_orders",
        help_text="The dock/staging area the goods land on and leave from — no bin in between")
    quantity = models.DecimalField(
        max_digits=16, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=4, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="Inbound cost per unit — becomes the receipt's cost layer")
    scheduled_date = models.DateField(help_text="Planned dock date")
    inbound_reference = models.CharField(
        max_length=40, blank=True,
        help_text="Where the goods come from, e.g. GRN-00012 / PO-00007")
    outbound_reference = models.CharField(
        max_length=40, blank=True,
        help_text="Where the goods go, e.g. SO-00031 / SHP-00004")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    received_at = models.DateTimeField(null=True, blank=True, editable=False)
    shipped_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="inv_xd_tnt_status_idx")]

    # -- state ---------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """The badge class for this row's status — see :attr:`STATUS_CSS`."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    def ledger_moves(self):
        """This order's StockMove legs, newest first — the audit-proof record of the flow."""
        from apps.scm.models import StockMove
        return (StockMove.objects.filter(tenant_id=self.tenant_id, reference=self.number)
                .select_related("item", "location").order_by("-moved_at", "-id"))

    def clean(self):
        super().clean()
        if self.dock_location_id and self.dock_location.tenant_id != self.tenant_id:
            raise ValidationError({"dock_location": "That location belongs to another workspace."})
        if self.lot_serial_id:
            if self.lot_serial.tenant_id != self.tenant_id:
                raise ValidationError({"lot_serial": "That lot/serial belongs to another workspace."})
            if self.item_id and self.lot_serial.item_id != self.item_id:
                raise ValidationError({"lot_serial": "That lot/serial belongs to a different item."})

    # -- ledger posting ------------------------------------------------------------------------

    def _post_move(self, *, location, quantity, move_type, reason, unit_cost=None):
        """Append ONE signed StockMove leg. Assumes an enclosing transaction.atomic().

        Mirrors SCM's single posting service where it matters: an inbound move rolls the
        item's cached weighted-average cost forward FIRST (against pre-move on-hand), and
        ``unit_cost`` is tested with ``is not None`` so a genuinely free receipt still
        dilutes the average instead of being read as "no cost given".
        """
        from apps.scm.models import StockMove
        quantity = quantity or ZERO
        cost = self.unit_cost if unit_cost is None else unit_cost
        if quantity > ZERO and cost is not None:
            self.item.apply_receipt(quantity, cost)
        return StockMove.objects.create(
            tenant_id=self.tenant_id, item=self.item, location=location,
            lot_serial=self.lot_serial, quantity=quantity, unit_cost=cost or ZERO,
            move_type=move_type, reference=self.number, reason=reason,
            moved_at=timezone.now(),
        )

    def _locked(self):
        """Re-read this row FOR UPDATE inside the caller's atomic block.

        Every action guards on a column of the ROW, so the guard must run against the
        locked re-read — the snapshot ``self`` carries could be stale by the time the
        lock is granted and two racing POSTs would each pass it.
        """
        return type(self).objects.select_for_update().get(pk=self.pk)

    # -- actions (called by the views, which flash + audit around them) ------------------------

    def receive(self, user):
        """Post the inbound leg: the trailer is unloaded onto the dock."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status != "draft":
                raise ValidationError(
                    f"{obj.number} cannot be received — it is {obj.get_status_display().lower()}.")
            obj._post_move(location=obj.dock_location, quantity=obj.quantity,
                           move_type="receipt", reason="Cross-dock receipt")
            obj.status = "received"
            obj.received_at = timezone.now()
            obj.save(update_fields=["status", "received_at", "updated_at"])
            write_audit_log(user, obj, "receive", {"status": "received"})
        return obj

    def ship(self, user):
        """Post the outbound leg: the goods leave the dock for their outbound reference."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status != "received":
                raise ValidationError(
                    f"{obj.number} cannot be shipped — it is {obj.get_status_display().lower()}; "
                    f"receive it first.")
            shortfall = _shortfall(obj.item, obj.dock_location, obj.quantity, obj.lot_serial)
            if shortfall:
                raise ValidationError(shortfall)
            obj._post_move(location=obj.dock_location, quantity=-obj.quantity,
                           move_type="issue", reason="Cross-dock dispatch",
                           unit_cost=obj.item.average_cost or ZERO)
            obj.status = "shipped"
            obj.shipped_at = timezone.now()
            obj.save(update_fields=["status", "shipped_at", "updated_at"])
            write_audit_log(user, obj, "ship", {"status": "shipped"})
        return obj

    def cancel(self, user):
        """Refuse the flow. From draft this is a paper cancellation; from received it also
        reverses the receipt with a GUARDED compensating move — the ledger is append-only,
        so nothing is ever deleted."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status not in obj.CANCELLABLE_STATUSES:
                raise ValidationError(
                    f"{obj.number} cannot be cancelled — it is {obj.get_status_display().lower()}.")
            was_received = obj.status == "received"
            if was_received:
                shortfall = _shortfall(obj.item, obj.dock_location, obj.quantity, obj.lot_serial)
                if shortfall:
                    raise ValidationError(
                        f"Cannot cancel — some of it has already moved on. {shortfall}")
                obj._post_move(location=obj.dock_location, quantity=-obj.quantity,
                               move_type="receipt", reason="Cross-dock cancelled")
            obj.status = "cancelled"
            obj.save(update_fields=["status", "updated_at"])
            write_audit_log(user, obj, "cancel",
                            {"status": "cancelled", "reversed_receipt": was_received})
        return obj

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{self.number or 'XD'} · {sku} ×{self.quantity}"
