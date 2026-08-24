"""Inventory 5.15 Quality Control (QC) & Inspection — QuarantineOrder [QRD-].

**Quarantine Management** bullet: physically segregate suspect stock in a restricted area
until quality clears it. SCM 4.9's NCR ruling is explicit (``apps/scm/models/NonConformances.py``):
a quarantine there posts NOTHING — it flips ``LotSerial.status``, and *physical segregation,
if wanted, is an ordinary transfer into a QC-hold location*. This document IS that wanted
segregation, as an operational order: its lifecycle posts REAL legs into 4.3's append-only
ledger (L36/L29) exactly the way 5.5's CrossDockOrder does::

    draft ──quarantine()──▶ quarantined ──release()──▶ released   (goods cleared, go back)
      │                        │
      │                        └──scrap()──▶ scrapped         (−adjustment at the QC zone)
      └──cancel()──────────────┘   (quarantined: reverses the pair — reversal pattern)

The −/+ pairs are ``transfer`` moves at the item's average cost (value-neutral by
construction, mirroring ``scm.views._helpers._post_transfer``); the scrap leg is a negative
``adjustment`` — no new move type, per the NCR ruling. On-hand stays a pure ledger aggregate;
nothing here stores a quantity of its own.

Every action re-reads its row FOR UPDATE inside the atomic block before guarding (a
double-clicked button cannot post a hold twice), locks the Item row so racing postings on
one stock pool serialize, and writes its audit row INSIDE the transaction.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403


def _shortfall(item, location, quantity, lot_serial=None):
    """Message when ``location`` can't cover an outbound ``quantity``, else ''.

    Same rule as scm's posting service (kept local, like 5.5's copy): scoped to
    (item, location) AND the named lot when there is one. Reads the live aggregate,
    so moves posted earlier in the same transaction count.
    """
    qs = item.stock_moves.filter(location=location)
    if lot_serial is not None:
        qs = qs.filter(lot_serial=lot_serial)
    available = qs.aggregate(q=Sum("quantity"))["q"] or ZERO
    if quantity > available:
        where = f"{lot_serial.number} at {location.code}" if lot_serial is not None else location.code
        return f"{item.sku}: only {available} available at {where}, cannot move {quantity}."
    return ""


class QuarantineOrder(TenantNumbered):
    """One segregation of suspect stock into a restricted QC zone [QRD-]."""

    NUMBER_PREFIX = "QRD"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("quarantined", "Quarantined"),
        ("released", "Released"),
        ("scrapped", "Scrapped"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft",)
    #: Statuses cancel() accepts — once released/scrapped, only a compensating document undoes it.
    CANCELLABLE_STATUSES = ("draft", "quarantined")

    #: Badge colour per status, decided in ONE place (colour-named modifiers ONLY — L33).
    STATUS_CSS = {
        "draft": "badge-slate",
        "quarantined": "badge-amber",
        "released": "badge-green",
        "scrapped": "badge-red",
        "cancelled": "badge-muted",
    }

    REASON_CHOICES = [
        ("suspected_defect", "Suspected Defect"),
        ("damage_found", "Damage Found in Stock"),
        ("customer_return", "Customer Return Pending Inspection"),
        ("qc_hold", "QC Hold — Awaiting Inspection"),
        ("compliance_hold", "Compliance / Regulatory Hold"),
        ("other", "Other"),
    ]

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, related_name="inventory_quarantine_orders",
        help_text="The suspect product")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_quarantine_orders",
        help_text="Optional lot/serial for tracked items")
    source_location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="inventory_quarantine_sources",
        help_text="Where the goods sit NOW — the outbound half of the hold pair")
    quarantine_location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="inventory_quarantine_orders",
        help_text="The restricted QC zone they are segregated INTO")
    quantity = models.DecimalField(
        max_digits=16, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    reason = models.CharField(max_length=18, choices=REASON_CHOICES, default="qc_hold")
    reference = models.CharField(
        max_length=40, blank=True,
        help_text="Source document number, e.g. GRN-00012 / RMA-00004 / NCR-00002")
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=11, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    quarantined_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False,
                                       help_text="Release / scrap / cancel moment")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_qro_tnt_status_idx"),
            models.Index(fields=["tenant", "item"], name="inv_qro_tnt_item_idx"),
        ]

    # -- state ---------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """The badge class for this row's status — see :attr:`STATUS_CSS`."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    def ledger_moves(self):
        """This order's StockMove legs, newest first — the audit-proof record."""
        from apps.scm.models import StockMove
        return (StockMove.objects.filter(tenant_id=self.tenant_id, reference=self.number)
                .select_related("item", "location").order_by("-moved_at", "-id"))

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        errors = {}
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            errors["item"] = "That item belongs to another workspace."
        if self.source_location_id and getattr(self.source_location, "tenant_id", None) != tenant_id:
            errors["source_location"] = "That location belongs to another workspace."
        if (self.quarantine_location_id
                and getattr(self.quarantine_location, "tenant_id", None) != tenant_id):
            errors["quarantine_location"] = "That location belongs to another workspace."
        if self.lot_serial_id:
            if getattr(self.lot_serial, "tenant_id", None) != tenant_id:
                errors["lot_serial"] = "That lot/serial belongs to another workspace."
            elif self.item_id and self.lot_serial.item_id != self.item_id:
                errors["lot_serial"] = f"{self.lot_serial.number} belongs to a different item."
        if (self.source_location_id and self.quarantine_location_id
                and self.source_location_id == self.quarantine_location_id):
            errors["quarantine_location"] = "The QC zone must differ from the source location — " \
                                            "holding goods where they already sit segregates nothing."
        if errors:
            raise ValidationError(errors)

    # -- ledger posting ------------------------------------------------------------------------

    def _post_leg(self, *, location, quantity, move_type, reason, unit_cost):
        """Append ONE signed StockMove leg. Assumes an enclosing transaction.atomic().

        Transfer legs carry the item's average cost (scm's own transfer convention);
        apply_receipt with that same figure is value-neutral, so the cached average
        never drifts on a mere move between bins.
        """
        from apps.scm.models import StockMove
        return StockMove.objects.create(
            tenant_id=self.tenant_id, item=self.item, location=location,
            lot_serial=self.lot_serial, quantity=quantity, unit_cost=unit_cost or ZERO,
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

    def _stock_lock(self):
        """Lock the Item row FOR UPDATE inside the caller's atomic block.

        Serializes balance-checked postings sharing one stock pool (5.5 precedent).
        """
        from apps.scm.models import Item
        return Item.objects.select_for_update().get(pk=self.item_id)

    def _reverse_pair(self, obj, reason_prefix):
        """Post the release/reversal pair back out of the QC zone.

        Only the OUT leg can fail: the goods must still be sitting in the QC zone.
        The return leg merely ADDS stock back at the source, so it needs no guard.
        """
        cost = obj.item.average_cost or ZERO
        shortfall = _shortfall(obj.item, obj.quarantine_location, obj.quantity, obj.lot_serial)
        if shortfall:
            raise ValidationError(f"Cannot return from quarantine — {shortfall}")
        obj._post_leg(location=obj.quarantine_location, quantity=-obj.quantity,
                      move_type="transfer", reason=f"{reason_prefix} — out", unit_cost=cost)
        obj._post_leg(location=obj.source_location, quantity=obj.quantity,
                      move_type="transfer", reason=f"{reason_prefix} — back in", unit_cost=cost)

    # -- actions (called by the views, which flash + audit around them) -------------------------

    def quarantine(self, user):
        """Hold the goods: post the −/+ pair moving them into the restricted zone."""
        with transaction.atomic():
            obj = self._locked()
            _item_lock = obj._stock_lock()
            if obj.status != "draft":
                raise ValidationError(
                    f"{obj.number} cannot be quarantined — it is "
                    f"{obj.get_status_display().lower()}.")
            shortfall = _shortfall(obj.item, obj.source_location, obj.quantity, obj.lot_serial)
            if shortfall:
                raise ValidationError(shortfall)
            cost = obj.item.average_cost or ZERO
            obj._post_leg(location=obj.source_location, quantity=-obj.quantity,
                          move_type="transfer", reason="Quarantine hold — out", unit_cost=cost)
            obj._post_leg(location=obj.quarantine_location, quantity=obj.quantity,
                          move_type="transfer", reason="Quarantine hold — in", unit_cost=cost)
            obj.status = "quarantined"
            obj.quarantined_at = timezone.now()
            obj.save(update_fields=["status", "quarantined_at", "updated_at"])
            write_audit_log(user, obj, "quarantine",
                            {"status": "quarantined", "quantity": str(obj.quantity)})
        return obj

    def release(self, user):
        """Quality cleared it: return every held unit to where they came from."""
        with transaction.atomic():
            obj = self._locked()
            _item_lock = obj._stock_lock()
            if obj.status != "quarantined":
                raise ValidationError(
                    f"{obj.number} cannot be released — it is {obj.get_status_display().lower()}; "
                    f"quarantine it first.")
            self._reverse_pair(obj, "Quarantine released")
            obj.status = "released"
            obj.resolved_at = timezone.now()
            obj.save(update_fields=["status", "resolved_at", "updated_at"])
            write_audit_log(user, obj, "release", {"status": "released"})
        return obj

    def scrap(self, user):
        """Quality condemned it: write the held units off FROM the QC zone.

        Mirrors the NCR scrap ruling — a negative ``adjustment`` move, no new type —
        scoped to exactly what THIS order moved in, so an NCR raised separately can
        never double-post the same units.
        """
        with transaction.atomic():
            obj = self._locked()
            _item_lock = obj._stock_lock()
            if obj.status != "quarantined":
                raise ValidationError(
                    f"{obj.number} cannot be scrapped — it is {obj.get_status_display().lower()}; "
                    f"quarantine it first.")
            shortfall = _shortfall(obj.item, obj.quarantine_location, obj.quantity, obj.lot_serial)
            if shortfall:
                raise ValidationError(shortfall)
            obj._post_leg(location=obj.quarantine_location, quantity=-obj.quantity,
                          move_type="adjustment", reason="Scrapped from quarantine",
                          unit_cost=obj.item.average_cost or ZERO)
            obj.status = "scrapped"
            obj.resolved_at = timezone.now()
            obj.save(update_fields=["status", "resolved_at", "updated_at"])
            write_audit_log(user, obj, "scrap", {"status": "scrapped"})
        return obj

    def cancel(self, user):
        """Refuse the hold. From draft this is paper-only; from quarantined it returns
        the goods first — the ledger is append-only, so nothing is ever deleted."""
        with transaction.atomic():
            obj = self._locked()
            _item_lock = obj._stock_lock()
            if obj.status not in self.CANCELLABLE_STATUSES:
                raise ValidationError(
                    f"{obj.number} cannot be cancelled — it is "
                    f"{obj.get_status_display().lower()}.")
            was_held = obj.status == "quarantined"
            if was_held:
                self._reverse_pair(obj, "Quarantine cancelled")
            obj.status = "cancelled"
            obj.resolved_at = timezone.now()
            obj.save(update_fields=["status", "resolved_at", "updated_at"])
            write_audit_log(user, obj, "cancel",
                            {"status": "cancelled", "reversed_hold": was_held})
        return obj

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{self.number or 'QRD'} · {sku} ×{self.quantity}"
