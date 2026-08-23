"""Inventory 5.9 Order Management & Fulfillment — FulfillmentWave + FulfillmentWaveOrder.

Three of the four NavERP bullets are SCM documents this module must never re-declare
(L36): the order is 4.5's ``SalesOrder``, the pick/pack/dispatch is 4.4's ``PickTask``,
the ship method is 4.6's ``Carrier`` master. What nothing else records is the WAVE: a
planner's decision to release a batch of orders to the floor together, with one cutoff,
one carrier and one set of entry criteria. That is ONE header (``FulfillmentWave``
[WAV-]) and ONE child row per member order (``FulfillmentWaveOrder``) — nothing more.

**ZERO writes into scm.** release()/close()/cancel() flip only the wave's own status;
attaching picks stays SCM's side, where an operator types ``wave_ref = WAV-#####`` into
``scm:picktask_edit``. The wave↔pick link is therefore a DOCUMENTED TEXT CONVENTION
(``PickTask.wave_ref == wave.number``, case-sensitive — ``scm_pik_tnt_wave_idx`` exists
for exactly this lookup), never an invented FK, which would cost an scm migration.

The honesty rules this file owns:

* **Progress answers ``None``, never a flattering zero.** ``pick_progress_pct`` refuses
  to divide when no linked picks exist yet; the templates render "—" until scm speaks.
* **Cancelled orders are never progress.** ``orders_fulfilled_count`` counts members in
  the fulfilled-or-later vocabulary pinned from ``scm.SalesOrder.STATUS_CHOICES``;
  "cancelled" is deliberately absent from it.
* **Every action re-reads its row FOR UPDATE inside the atomic block** before guarding,
  so two racing POSTs cannot both pass the status check, and every action writes its
  audit row INSIDE the transaction, so a committed flip always has its trail.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403
# BY NAME from the owning SCM module — the same route Loads/Shipments take for their
# transport vocabularies (Carriers.py defines them; the scm package root does not
# re-export constants). One-way dependency, no cycle.
from apps.scm.models.TransportationManagement.Carriers import SERVICE_LEVEL_CHOICES


class FulfillmentWave(TenantNumbered):
    """One planned-to-floor release of sales orders [WAV-], with criteria and a cutoff.

    A wave is an OPERATIONAL DECISION about grouping, not stock and not an order: it
    stores no quantities and posts nothing anywhere. Its whole value is the derived
    picture — how many member orders, how many already fulfilled downstream, how far
    the floor has picked against the text convention above.

    Lifecycle::

        planned ──release()──▶ released ──close()──▶ closed
           │                      │
           └────────cancel()──────┘

    Membership locks at release (Odoo's lock-after-release lesson): adding or removing
    orders once the floor may be working the list would silently change what the wave
    promised, so only a ``planned`` wave accepts membership changes.
    """

    NUMBER_PREFIX = "WAV"

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("released", "Released"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("planned",)
    #: Statuses cancel() accepts — a closed wave is finished history, not cancellable.
    CANCELLABLE_STATUSES = ("planned", "released")

    #: FROZEN from ``scm.SalesOrder.STATUS_CHOICES``: the fulfilled-or-later rung set.
    #: "cancelled" is deliberately NOT progress; "submitted"/"allocated"/"on_hold" are
    #: still work-in-queue, not fulfilment.
    FULFILLED_STATUSES = ("partially_fulfilled", "fulfilled", "invoiced", "closed")

    #: scm.PickTask statuses that count as "done" for wave pick progress — frozen from
    #: PickTask.STATUS_CHOICES (dispatch happens after pack, so packed is the terminal
    #: signal this module can honestly read).
    PICK_DONE_STATUSES = ("picked", "packed")

    #: Badge colour per status, decided in ONE place. theme.css ships colour-named badge
    #: modifiers only — semantic -success/-warning variants do not exist and render
    #: unstyled (lesson L33).
    STATUS_CSS = {
        "planned": "badge-slate",
        "released": "badge-info",
        "closed": "badge-green",
        "cancelled": "badge-red",
    }

    status = models.CharField(max_length=12, choices=STATUS_CHOICES,
                              default="planned", editable=False)
    description = models.CharField(max_length=255, blank=True)
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_waves",
        help_text="Warehouse the wave ships from")
    carrier = models.ForeignKey(
        "scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_waves",
        help_text="Carrier tendered for the whole wave (4.6 TCS master)")
    ship_method = models.CharField(max_length=12, choices=SERVICE_LEVEL_CHOICES,
                                   blank=True, default="")
    planned_ship_date = models.DateField(null=True, blank=True)
    cutoff_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Orders must be picked by this moment to make the truck")
    priority = models.PositiveIntegerField(default=100)
    criteria_text = models.TextField(
        blank=True,
        help_text="What qualifies an order for this wave, in the planner's words")
    released_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="inv_wav_tnt_status_idx")]

    # -- state ---------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """The badge class for this row's status — see :attr:`STATUS_CSS`."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    def clean(self):
        """Per-field cross-tenant rejection keyed on the raw ``<name>_id``, so the error
        renders where the user is looking and attribute access on a crafted/unset FK can
        never escape full_clean() as a non-ValidationError 500 (5.4 C1 pattern)."""
        super().clean()
        errors = {}
        for name in ("location", "carrier"):
            if getattr(self, f"{name}_id") is None:
                continue
            chosen = getattr(self, name)
            if chosen.tenant_id != self.tenant_id:
                errors[name] = "That record belongs to another workspace."
        if errors:
            raise ValidationError(errors)

    # -- derived picture (None-honest, never stored) -------------------------------------------

    @property
    def member_order_count(self):
        return self.orders.count()

    @property
    def orders_fulfilled_count(self):
        """Members whose sales order has reached a fulfilled-or-later rung — see
        :attr:`FULFILLED_STATUSES`. Cancelled is deliberately not counted as progress."""
        return self.orders.filter(
            sales_order__status__in=self.FULFILLED_STATUSES).count()

    @property
    def pick_progress_pct(self):
        """picked+packed over non-cancelled matched picks, as an int percent — or None.

        None means "no signal yet": no ``scm.PickTask`` carries this wave's number in
        its free-text ``wave_ref`` (the L28 convention documented in this file's
        docstring), so there is nothing honest to divide. Zero linked picks MUST NOT
        render as 0% — that would accuse the floor of doing nothing when nobody has
        typed the reference yet."""
        if not self.number:
            return None
        from apps.scm.models import PickTask
        agg = (PickTask.objects.filter(tenant_id=self.tenant_id, wave_ref=self.number)
               .aggregate(total=Count("id"),
                          done=Count("id", filter=Q(status__in=self.PICK_DONE_STATUSES)),
                          active=Count("id", filter=~Q(status="cancelled"))))
        if not agg["total"]:
            return None
        return pick_progress_pct_from(agg["done"], agg["active"])

    def linked_picks(self):
        """The picks matched through the wave_ref==number text convention, newest first.

        A query, not a property, because it hits scm — callers that need several waves'
        progress should group over PickTask once instead of calling this per row."""
        from apps.scm.models import PickTask
        if not self.number:
            return PickTask.objects.none()
        return (PickTask.objects.filter(tenant_id=self.tenant_id, wave_ref=self.number)
                .select_related("zone").order_by("-created_at", "-id"))

    # -- actions ---------------------------------------------------------------------------------

    def _locked(self):
        """Re-read this row FOR UPDATE inside the caller's atomic block.

        Every action guards on a column of the ROW, so the guard must run against the
        locked re-read — the snapshot ``self`` carries could be stale by the time the
        lock is granted and two racing POSTs would each pass it (CrossDockOrder pattern).
        """
        return type(self).objects.select_for_update().get(pk=self.pk)

    def release(self, user):
        """Release the wave to the floor: planned → released, stamped ``released_at``.

        Refuses a zero-member wave — releasing an empty grouping would stamp a promise
        with nothing in it. Does NOT touch any scm row: handing picks their wave_ref is
        the operator's next action IN scm."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status != "planned":
                raise ValidationError(
                    f"{obj.number} cannot be released — it is {obj.get_status_display().lower()}.")
            if not obj.orders.exists():
                raise ValidationError(
                    f"{obj.number} cannot be released — it has no sales orders attached.")
            obj.status = "released"
            obj.released_at = timezone.now()
            obj.save(update_fields=["status", "released_at", "updated_at"])
            write_audit_log(user, obj, "release", {"status": "released"})
        return obj

    def close(self, user):
        """Everything shipped: released → closed, stamped ``closed_at``. Closing is
        bookkeeping, not posting — it writes nothing outside this row."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status != "released":
                raise ValidationError(
                    f"{obj.number} cannot be closed — it is {obj.get_status_display().lower()}; "
                    f"release it first.")
            obj.status = "closed"
            obj.closed_at = timezone.now()
            obj.save(update_fields=["status", "closed_at", "updated_at"])
            write_audit_log(user, obj, "close", {"status": "closed"})
        return obj

    def cancel(self, user):
        """Refuse the wave. From planned this is a paper cancellation; from released the
        floor may have started picking under the wave_ref convention, but those picks are
        scm documents — cancelling here flips nothing but this row's own state."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status not in obj.CANCELLABLE_STATUSES:
                raise ValidationError(
                    f"{obj.number} cannot be cancelled — it is {obj.get_status_display().lower()}.")
            was_released = obj.status == "released"
            obj.status = "cancelled"
            obj.closed_at = timezone.now()
            obj.save(update_fields=["status", "closed_at", "updated_at"])
            write_audit_log(user, obj, "cancel",
                            {"status": "cancelled", "was_released": was_released})
        return obj

    def __str__(self):
        # member_order_count is a query — unsaved rows (admin preview, in-memory
        # construction) have no members to count and no pk to query through.
        members = self.member_order_count if self.pk else 0
        return f"{self.number or 'WAV'} · {members} order(s)"


class FulfillmentWaveOrder(models.Model):
    """One sales order's membership in one wave — the child row that makes the wave real.

    Deliberately its own table rather than a reverse pointer on SalesOrder: the order
    spine belongs to 4.5 and gains NO column from Module 5. ``tenant`` is declared
    explicitly (not inherited) so the child carries its own scoped column exactly like
    StockTransferLine — children reached through a parent still get filtered by tenant
    in every direct queryset."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="fulfillment_wave_orders")
    wave = models.ForeignKey("inventory.FulfillmentWave", on_delete=models.CASCADE,
                             related_name="orders")
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.PROTECT,
                                    related_name="inventory_wave_orders",
                                    help_text="The customer order travelling with this wave")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="+",
                                 help_text="Who put the order into the wave")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["id"]
        unique_together = ("wave", "sales_order")

    def clean(self):
        """Cross-tenant rejection on the one chosen FK + the release lock: membership
        freezes the moment the wave leaves ``planned`` (enforced here for non-form
        writers too — admin, seeder), not just in the form/view layer."""
        super().clean()
        errors = {}
        if self.sales_order_id and self.sales_order.tenant_id != self.tenant_id:
            errors["sales_order"] = "That record belongs to another workspace."
        if self.wave_id and self.wave.status != "planned":
            errors["__all__"] = (
                f"{self.wave.number} is {self.wave.get_status_display().lower()} — "
                f"its membership can no longer be changed.")
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.wave.number} · {self.sales_order.number}"


def pick_progress_pct_from(done, active):
    """Shared percentage rule for :meth:`FulfillmentWave.pick_progress_pct` and the board.

    ``(done / active) * 100`` rounded to an int, or None when there is no denominator —
    the single place the "None, never 0%" honesty rule lives, so the model property and
    the precomputed board rows can never drift apart."""
    if not active:
        return None
    return int(round(done * 100 / active))
