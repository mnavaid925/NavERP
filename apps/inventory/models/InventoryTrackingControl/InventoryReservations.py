"""Inventory 5.6 Inventory Tracking & Control — InventoryReservation.

**Inventory Reservations** bullet: locking specific quantities of stock for specific
sales orders or jobs. ``scm.SalesOrderAllocation`` (4.5) is the order-management path
— created automatically during order promising, tied to an SO LINE. This is the control-
layer tool beside it: a general-purpose claim against ANY reference (a sales order,
a job/work order, a project, or a manual hold), raised by hand when someone needs units
set aside before any document exists to promise them.

Same soft-claim discipline as the spine's allocation (L37): posting one creates NO
``StockMove``. The ledger stays the single source of physical truth; what drops is
availability-to-promise, which the Real-Time Stock Levels page derives as
``on_hand − active claims (allocations AND reservations) − non-sellable classifications``.
Stock only ever physically leaves through whichever outbound document actually issues it.

Lifecycle::

    reserved ──release()──▶ released ──consume()──▶ consumed
       │          │              │                         (claim closed: the goods left)
       └──────────┴──────────────┴──────cancel()───────── cancelled

``released`` mirrors 4.5's meaning — handed off to the floor for fulfillment, still
counting as allocated until the physical move posts. ``consumed`` stops counting,
because the issuing document has already reduced on-hand; counting it too would dock
availability twice for the same units.

Every action re-reads its row FOR UPDATE inside the atomic block before guarding, so a
double-clicked button cannot advance the lifecycle twice.
"""
from django.conf import settings
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403


class InventoryReservation(TenantNumbered):
    """One soft lock of stock against a reference [RSV-] [of 5.6]."""

    NUMBER_PREFIX = "RSV"

    PURPOSE_CHOICES = [
        ("sales_order", "Sales Order"),
        ("job", "Job / Work Order"),
        ("project", "Project"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("reserved", "Reserved"),
        ("released", "Released to Floor"),
        ("consumed", "Consumed"),
        ("cancelled", "Cancelled"),
    ]
    #: Statuses that still hold stock back from availability (see module docstring).
    ACTIVE_STATUSES = ("reserved", "released")
    #: Statuses edit() may touch — once consumed/cancelled the row is history.
    EDITABLE_STATUSES = ("reserved",)
    #: Statuses release/consume/cancel accept.
    ACTIONABLE_STATUSES = ("reserved", "released")

    #: Badge colour per status, decided in ONE place. theme.css ships colour-named badge
    #: modifiers only (green/red/amber/info/muted/slate) — the semantic -success/-warning/
    #: -danger variants do not exist and render unstyled (lesson L33).
    STATUS_CSS = {
        "reserved": "badge-info",
        "released": "badge-amber",
        "consumed": "badge-green",
        "cancelled": "badge-slate",
    }

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, related_name="reservations",
        help_text="The item whose stock is being locked")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="reservations",
        help_text="The spot the reserved units are held at")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reservations",
        help_text="Optional lot/serial for tracked items")
    purpose = models.CharField(max_length=12, choices=PURPOSE_CHOICES, default="sales_order")
    reference = models.CharField(
        max_length=64, blank=True,
        help_text="The document the stock is locked for, e.g. SO-00031 / JOB-0042")
    quantity = models.DecimalField(
        max_digits=16, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="reserved",
                              editable=False)
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_reservations",
        help_text="Who raised the lock")
    notes = models.CharField(max_length=255, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_rsv_tnt_status_idx"),
            models.Index(fields=["tenant", "item", "location"], name="inv_rsv_tnt_item_loc_idx"),
        ]

    # -- state ---------------------------------------------------------------------------------

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """The badge class for this row's status — see :attr:`STATUS_CSS`."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    def clean(self):
        super().clean()
        # The form's _reject_foreign covers user input; these checks cover every OTHER
        # write path (admin, seeder, a future import) that could attach another
        # workspace's row to this claim.
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})
        if self.location_id and self.location.tenant_id != self.tenant_id:
            raise ValidationError({"location": "That location belongs to another workspace."})
        if self.lot_serial_id:
            if self.lot_serial.tenant_id != self.tenant_id:
                raise ValidationError({"lot_serial": "That lot/serial belongs to another workspace."})
            if self.item_id and self.lot_serial.item_id != self.item_id:
                raise ValidationError({"lot_serial": "That lot/serial belongs to a different item."})

    # -- actions (called by the views, which flash + audit around them) ------------------------

    def _locked(self):
        """Re-read this row FOR UPDATE inside the caller's atomic block.

        Every action guards on a column of the ROW, so the guard must run against the
        locked re-read — the snapshot ``self`` carries could be stale by the time the
        lock is granted and two racing POSTs would each pass it.
        """
        return type(self).objects.select_for_update().get(pk=self.pk)

    def _advance(self, user, target):
        """Move one lifecycle step under lock, refusing anything else.

        The ``status == target`` arm matters as much as the ACTIONABLE guard: release()
        on an already-released row would otherwise re-write ``resolved_at`` and append a
        second identical audit entry every time it was double-clicked — consume/cancel
        were already terminal-guarded, released-to-released was the one hole.
        """
        with transaction.atomic():
            obj = self._locked()
            if obj.status == target or obj.status not in obj.ACTIONABLE_STATUSES:
                raise ValidationError(
                    f"{obj.number} cannot move to {obj._target_label(target)} — it is "
                    f"{obj.get_status_display().lower()}.")
            obj.status = target
            obj.resolved_at = None if target == "released" else timezone.now()
            obj.save(update_fields=["status", "resolved_at", "updated_at"])
            write_audit_log(user, obj, target, {"status": target})
        return obj

    @staticmethod
    def _target_label(target):
        return {"released": "released", "consumed": "consumed", "cancelled": "cancelled"}[target]

    def release(self, user):
        """Hand the locked units to the floor — still allocated until goods physically move."""
        return self._advance(user, "released")

    def consume(self, user):
        """Close the claim: the outbound document has issued the goods (and posted ITS move)."""
        return self._advance(user, "consumed")

    def cancel(self, user):
        """Drop the claim without fulfilling — frees the availability it was holding."""
        return self._advance(user, "cancelled")

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        where = self.location.code if self.location_id else "?"
        return f"{self.number or 'RSV'} · {sku} ×{self.quantity} @ {where}"
