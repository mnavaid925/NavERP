"""Sales 8.6 Order Management — the change order: ``OrderAmendment`` + ``OrderAmendmentLine``.

SCM 4.5 owns the sales order and said so in writing, twice: the module docstring of
``apps/scm/models/OrderManagement/SalesOrders.py`` and lines 44-47 of the same file, which
record that there is *"deliberately NO amendment flow here — amend/cancel with impact
analysis is Module 8.6's job"*. This file is that job, and it is built as an EXTENSION:

* ``sales_order`` is an FK **into** ``scm.SalesOrder``. No second order master is declared,
  constructed or duplicated anywhere in this file (L36/L37). The order is read through the FK
  and re-derived from its own lines; 8.6 never invents a parallel copy of one.
* ``apply()`` is the **single writer** of ``SalesOrderLine.quantity_ordered`` and
  ``unit_price`` — the two columns 4.5 does not expose on an editable order. Totals are NOT
  recomputed here with our own arithmetic: ``apply()`` calls 4.5's own
  ``locked_order.recalc_totals()`` and then ``recompute_allocation_status()``, so the
  subtotal/tax/total formula and the allocation-derived status transitions stay in the code
  that owns them. Writing ``SalesOrder.status`` by hand from here would skip 4.5's guard and
  silently re-open a hole 4.5 closed.
* For ``change_type="cancel"`` the cancellation is **delegated**, not re-implemented: the same
  status write, the same notes append and the same ``has_active_allocations()`` refusal 4.5's
  ``salesorder_cancel`` performs, reproduced with a pointer back to that view. A second
  cancellation path is the failure mode §0.4 of the contract rules out.

``AMENDABLE_STATUSES`` is the eligibility rule, and it is read in exactly two places: here, by
``recompute_impact()`` / ``apply()``, and by the create form's ``sales_order`` dropdown. One
tuple, so "may this order be amended?" cannot answer yes on the form and no in the method.

**The impact snapshot is frozen evidence (L22).** ``impact_snapshot`` is written by the server
at propose time and every line it captures is a fact about the order *at that moment*: what
each line was, what the amendment proposes, how much of the order is already reserved, and how
far the total moves. It is ``editable=False``, absent from every form, and never recomputed on
read — so the ``impact.html`` page can show it BESIDE the live figures and the two can be seen
to disagree the moment somebody edits the order directly in SCM. A user-supplied impact blob
would be an account of the commercial consequence written by the person the consequence
happens to, which is worse than no account at all.

Every money figure here is computed in **PYTHON** over an already-fetched set — never with an
``F()`` expression, never with a database-side division. ``scm.SalesOrder.recalc_totals()``
documents the trap by name: on SQLite the integer division silently drops fractional cents
rather than raising.

Two validation traps are handled explicitly, and both are the 0.20 close-out lesson:

* ``OrderAmendment.clean()`` keys every message on a field that is actually on the form.
  It never raises against ``impact_snapshot`` or ``status`` — a ``ValidationError`` keyed on a
  field the form does not carry routes through ``add_error(None, …)``, which raises
  ``ValueError`` and 500s every create *and* edit. The snapshot's shape is normalised in
  ``save()`` instead of being validated in ``clean()``.
* ``OrderAmendmentLine.clean()`` is keyed on ``NON_FIELD_ERRORS`` for the same reason: its
  form excludes ``amendment`` (set by the parent view), so a guard keyed on the parent would be
  exactly the 0.20 four-statuses-500 shape.
"""
import json
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.forms.forms import NON_FIELD_ERRORS
from django.utils import timezone

from apps.sales.models._base import TenantNumbered


ZERO = Decimal("0")


def _money(value):
    """One money figure rendered JSON-safely, with the cents kept EXACT.

    ``impact_snapshot`` is a ``JSONField``, and ``json`` has no decimal type: a ``Decimal``
    handed to the encoder is coerced to a float, which is how ``"1999.99"`` quietly becomes
    ``1999.9899999999999`` in the very record a customer disputes six months later. Emitted as
    its own string instead. Anything unrecognised degrades to ``str()`` rather than raising — a
    snapshot that failed to build would lose the amendment, which is the one thing this record
    must never do.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def _qty(value):
    """A quantity rendered JSON-safely. Same reasoning as :func:`_money`."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


class OrderAmendment(TenantNumbered):
    """One change order against a live SCM sales order [AMD-]."""

    NUMBER_PREFIX = "AMD"

    #: The KIND of change, not its magnitude. ``quantity`` / ``price`` / ``add_line`` /
    #: ``remove_line`` each rewrite line figures; ``cancel`` is the one order-level move, and it
    #: is delegated to 4.5's own logic. The VALUE is what a badge or a fixture compares against.
    #:
    #: There is deliberately NO ``close``. 4.5's ``salesorder_close`` accepts exactly one status
    #: (``invoiced``), and ``invoiced`` is deliberately not in ``AMENDABLE_STATUSES``, so a Close
    #: amendment could never satisfy both rules at once. A dropdown choice that always refuses is
    #: worse than no choice — it advertises a verb that cannot fire. Closing stays 4.5's own
    #: action on the order page, once the invoice is settled. Do not re-add ``close`` without also
    #: revisiting ``AMENDABLE_STATUSES``, and do not widen that tuple to reach it: that would make
    #: every other amendment eligible against an invoiced order too.
    CHANGE_TYPE_CHOICES = [
        ("quantity", "Quantity Change"),
        ("price", "Price Change"),
        ("add_line", "Add Line"),
        ("remove_line", "Remove Line"),
        ("cancel", "Cancel Order"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("applied", "Applied"),
        ("withdrawn", "Withdrawn"),
        ("superseded", "Superseded"),
    ]

    #: An amendment changes a **live** customer commitment. A ``draft`` order is edited
    #: directly by 4.5 (its own ``EDITABLE_STATUSES``), and ``fulfilled`` / ``invoiced`` /
    #: ``cancelled`` / ``closed`` are terminal — a change order against any of them is a
    #: commercial event, not an edit. The create form's dropdown is narrowed to this same
    #: tuple, so the page and the method can never disagree about eligibility.
    AMENDABLE_STATUSES = ("submitted", "on_hold", "allocated", "partially_fulfilled")

    #: Statuses still accepting edits, lines, a decision or an application. A rejected,
    #: withdrawn, applied or superseded amendment is a closed document: it is read, never
    #: touched. ``has_open_for()`` and the detail page's ``can_*`` flags all read this tuple.
    OPEN_STATUSES = ("draft", "pending", "approved")

    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.CASCADE,
                                    related_name="order_amendments")
    change_type = models.CharField(max_length=16, choices=CHANGE_TYPE_CHOICES, default="quantity")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft", editable=False)
    reason = models.TextField()
    document = models.ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="order_amendments")
    # FROZEN EVIDENCE, server-generated at propose time. Never authorable (L22) and never
    # recomputed on read — see the module docstring.
    impact_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="order_amendments_requested",
                                     editable=False)
    requested_at = models.DateTimeField(default=timezone.now, editable=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="order_amendments_decided",
                                   editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The approver's own justification, written by the decision VERB. Deliberately NOT editable
    # on a ModelForm: an approval reason that a later form edit could rewrite is not evidence of
    # why the approver said yes (L22). Kept separate from ``notes`` (the change order's own notes)
    # so a rejection's reasoning is still legible after the amendment is applied and the notes are
    # appended to.
    decision_note = models.TextField(blank=True)
    applied_at = models.DateTimeField(null=True, blank=True, editable=False)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="order_amendments_applied",
                                   editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at", "-id"]
        constraints = [
            # NAMED, per MySQL's index-name ceiling: the auto-generated name for this pair is
            # long and machine-derived, and a constraint nobody can name in a hand-written
            # rollback is a constraint nobody drops.
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_amd_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_amd_tnt_status_idx"),
            models.Index(fields=["tenant", "sales_order"], name="sales_amd_tnt_order_idx"),
        ]

    # ------------------------------------------------------------------ state

    @property
    def is_open(self):
        """True while this amendment can still be edited, decided or applied."""
        return self.status in self.OPEN_STATUSES

    @property
    def parsed_impact(self) -> dict:
        """``impact_snapshot`` as a dict, or ``{}`` — never a raw string, never a raise.

        The same safety wrapper ``OrderHold.parsed_snapshot`` provides, under the name that
        matches this model's column. The column is a ``JSONField`` so Django normally hands
        back the parsed object already; this guards the two shapes that would otherwise blow
        up the one page whose whole job is to explain a commercial decision: a row written by a
        build that stored a bare string, and a hand-edited row holding a JSON array. Both the
        detail page and the impact page render THIS, so a malformed blob degrades to an empty
        panel rather than a 500.
        """
        raw = self.impact_snapshot
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, (str, bytes)):
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    # ------------------------------------------------------------------ lookups

    @classmethod
    def has_open_for(cls, sales_order, tenant, exclude_pk=None):
        """True when this order already carries an amendment that is still open.

        Two open change orders against one order is how two clerks end up applying
        contradictory quantities to the same line: the second one's impact analysis was taken
        against figures the first one has already moved. The create form refuses it, so the
        rule is a validation rather than a race.
        """
        if sales_order is None or getattr(sales_order, "pk", None) is None:
            return False
        queryset = cls.objects.filter(
            sales_order_id=sales_order.pk,
            status__in=cls.OPEN_STATUSES,
        )
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)
        if exclude_pk:
            queryset = queryset.exclude(pk=exclude_pk)
        return queryset.exists()


    # ------------------------------------------------------------------ impact

    def recompute_impact(self):
        """The impact read-out, computed in PYTHON over fetched sets. **Does not save.**

        Six keys the reader acts on, pinned by the contract:

        * ``lines`` — one entry per amendment line: what the order line IS and what the
          amendment PROPOSES, with the net delta of that line alone.
        * ``allocations_affected`` — active reservations sitting on the lines this amendment
          would move. Non-zero is not a block, it is a warning the approver must see: the
          warehouse is already holding stock against the old figure.
        * ``shipments_affected`` — shipments already raised against the order, i.e. physical
          commitments that will not move with the amendment.
        * ``delta_total`` — the change in the order's **grand** total, tax included, because
          that is the number the customer sees on the order.
        * ``revenue_impact`` — the change in the **net** contract value, tax excluded, because
          that is the number a revenue schedule recognises. Different figure, different reader:
          an amendment that moves tax alone has a revenue impact of zero and a total impact
          that is not.

        Plus a short identifying header (`captured_at`, `amendment`, `change_type` and the
        order's own number / status / totals as they stood at the moment of capture), so the
        frozen blob stays readable on its own months later.

        The caller writes this into ``impact_snapshot`` at propose time and nowhere else.
        """
        order = self.sales_order
        entries, delta_total, revenue_impact = [], ZERO, ZERO
        affected_lines = []

        for entry in self.lines.select_related("sales_order_line", "sales_order_line__item"):
            line = entry.sales_order_line
            old_qty = line.quantity_ordered if line is not None else ZERO
            old_price = line.unit_price if line is not None else ZERO
            discount = (line.discount_pct or ZERO) if line is not None else ZERO
            tax = (line.tax_pct or ZERO) if line is not None else ZERO

            if entry.operation == "add":
                new_qty = entry.new_quantity if entry.new_quantity is not None else ZERO
                new_price = entry.new_unit_price if entry.new_unit_price is not None else ZERO
            elif entry.operation == "remove":
                new_qty, new_price = ZERO, ZERO
            else:
                new_qty = entry.new_quantity if entry.new_quantity is not None else old_qty
                new_price = entry.new_unit_price if entry.new_unit_price is not None else old_price

            # The SAME formula 4.5's SalesOrderLine uses, re-derived in Python — a change order
            # that priced its own impact with a different rule than the order it is amending
            # would be an impact analysis nobody can reconcile to the order.
            net_factor = Decimal("1") - discount / Decimal("100")
            old_net = old_qty * old_price * net_factor
            new_net = new_qty * new_price * net_factor
            net_delta = new_net - old_net
            gross_delta = net_delta * (Decimal("1") + tax / Decimal("100"))

            delta_total += gross_delta
            revenue_impact += net_delta
            if line is not None and entry.operation != "add":
                affected_lines.append(line.pk)

        if self.change_type == "cancel":
            # A cancellation touches every reservation on the order, not just the named lines.
            allocations_affected = order.lines.filter(
                allocations__status__in=("reserved", "released")
            ).distinct().count()
        elif affected_lines:
            allocations_affected = order.lines.filter(
                pk__in=affected_lines, allocations__status__in=("reserved", "released")
            ).distinct().count()
        else:
            allocations_affected = 0

        return {
            "captured_at": timezone.now().isoformat(),
            "amendment": self.number or "",
            "change_type": self.change_type,
            "order_number": order.number,
            "order_status": order.status,
            "order_total": _money(order.total),
            "order_subtotal": _money(order.subtotal),
            "lines": entries,
            "allocations_affected": allocations_affected,
            "shipments_affected": self._shipments_affected(),
            "delta_total": _money(delta_total),
            "revenue_impact": _money(revenue_impact),
        }

    def _shipments_affected(self):
        """How many shipments already exist against the order, cancelled ones excluded.

        Read through SCM 4.6's table and guarded, because a change order that 500s on a
        missing sibling sub-module would lose the amendment itself — the one thing this record
        must never do.
        """
        if not self.sales_order_id:
            return 0
        try:
            from apps.scm.models import Shipment
        except ImportError:  # pragma: no cover - 4.6 is built, but never fail here
            return 0
        return Shipment.objects.filter(
            sales_order_id=self.sales_order_id
        ).exclude(status="cancelled").count()

    # ------------------------------------------------------------------ application

    def apply(self, user, locked_order, note=""):
        """Apply this amendment to ``locked_order`` and stamp it applied. THE SINGLE WRITER.

        ``locked_order`` is the row the **caller** took with ``select_for_update()``: the lock
        belongs to the transaction that opened it, and taking the order as an argument is what
        stops a second clerk from applying a second change order to figures this one has
        already moved.

        The rules are enforced here rather than in the view, because a guard that lives only in
        a view is a guard a caller can bypass:

        * ``status`` MUST be ``"approved"``. A draft, pending, rejected, withdrawn or
          already-applied amendment changes nothing.
        * the order MUST still be in ``AMENDABLE_STATUSES``. Approval was a decision taken
          against the order as it was; the order may have shipped, been invoiced or been
          cancelled since the approver read it.
        * ``change_type="cancel"`` refuses while ``has_active_allocations()`` and then delegates
          to 4.5's own cancellation, rather than writing the status itself.

        There is no ``close`` branch because there is no ``close`` choice — see
        ``CHANGE_TYPE_CHOICES`` for why a Close amendment could never be applied and why
        removing the choice beats shipping a dropdown entry that always refuses.

        Totals and allocation status are recomputed by 4.5's own methods — never by arithmetic
        re-implemented here. Returns a summary dict for the view's message and raises
        ``ValidationError`` (message-only, i.e. a non-field error) for every refusal, so a
        caller cannot miss one.
        """
        if self.status != "approved":
            raise ValidationError(
                f"Amendment {self.number or ''} is {self.get_status_display().lower()} — only an "
                "APPROVED amendment can be applied."
            )
        if locked_order is None or locked_order.pk != self.sales_order_id:
            raise ValidationError("The locked order does not match this amendment's order.")
        if locked_order.status not in self.AMENDABLE_STATUSES:
            raise ValidationError(
                f"Order {locked_order.number} is {locked_order.get_status_display().lower()}, "
                "which can no longer be amended. The approver decided against a different state "
                "of the order."
            )

        entries = list(self.lines.select_related("sales_order_line"))
        with transaction.atomic():
            if self.change_type == "cancel":
                self._apply_cancellation(locked_order, user, note)
            else:
                self._apply_line_changes(locked_order, entries)

            # 4.5's own arithmetic and 4.5's own status transitions. The subtotal/tax/total
            # formula and the allocation-derived statuses are NOT re-derived here — see the
            # module docstring.
            locked_order.recalc_totals()
            locked_order.recompute_allocation_status()

            self.status = "applied"
            self.applied_by = user
            self.applied_at = timezone.now()
            if note:
                self.notes = f"{self.notes}\nApplied: {note}".strip()
            self.save(update_fields=["status", "applied_by", "applied_at", "notes", "updated_at"])

        return {
            "cancelled": self.change_type == "cancel",
            "lines": len(entries),
            "order": locked_order.number,
        }

    def _apply_line_changes(self, locked_order, entries):
        """Write the quantity / price changes onto 4.5's order lines. Python, row by row."""
        for entry in entries:
            line = entry.sales_order_line
            if entry.operation == "add":
                # An ``add`` amendment has no original line by construction, so this is the
                # one place 8.6 CREATES an SCM row — and it creates only the writable columns
                # plus the two derived ones 4.5 needs to price a line. No item is guessed: an
                # unmapped line is 4.5's own visible to-do, and it refuses to submit one.
                from apps.scm.models import SalesOrderLine

                SalesOrderLine.objects.create(
                    sales_order=locked_order,
                    description=(entry.note or "Added by amendment")[:255],
                    quantity_ordered=entry.new_quantity or Decimal("1"),
                    unit_price=entry.new_unit_price or ZERO,
                )
                continue

            if line is None:
                # The original line was deleted in SCM after this amendment was proposed. The
                # proposal is now a no-op rather than a crash; the frozen impact snapshot
                # still shows what it was going to change.
                continue
            if line.sales_order_id != locked_order.pk:
                raise ValidationError(
                    "A line on this amendment does not belong to the order being amended."
                )
            if entry.operation == "remove":
                # Removing a line the warehouse is already reserving would leave stock promised
                # against a row that no longer exists. Refuse here; releasing the allocation is
                # 4.5's own cancel-allocation verb.
                if line.allocations.filter(status__in=("reserved", "released")).exists():
                    raise ValidationError(
                        f"Line {line.pk} still has stock allocated to it. Release or cancel the "
                        "allocations first, then remove the line."
                    )
                line.delete()
                continue

            fields = []
            if entry.new_quantity is not None and entry.new_quantity != line.quantity_ordered:
                line.quantity_ordered = entry.new_quantity
                fields.append("quantity_ordered")
            if entry.new_unit_price is not None and entry.new_unit_price != line.unit_price:
                line.unit_price = entry.new_unit_price
                fields.append("unit_price")
            if fields:
                line.save(update_fields=fields)

    def _apply_cancellation(self, locked_order, user, note):
        """Delegate the cancellation to 4.5's own logic.

        ``scm.views.salesorder_cancel`` is the single mutator (§0.4 of the contract) and it
        already refuses while ``has_active_allocations()``. Rather than call the view — which
        needs a request and flashes a message — the three things it does are reproduced here
        with a pointer back to it: the same refusal, the same status write, the same notes
        append naming the actor and the reason. Nothing in this method is 8.6's own idea of
        what cancelling an order means.
        """
        if locked_order.has_active_allocations():
            raise ValidationError(
                f"Order {locked_order.number} still has stock allocated to it. Cancel the "
                "allocations first, so the reserved stock is visibly released rather than "
                "silently dropped."
            )
        if locked_order.status in ("fulfilled", "invoiced", "cancelled", "closed"):
            raise ValidationError(
                f"Order {locked_order.number} has already shipped or closed and can't be cancelled."
            )
        reason = (note or self.reason or "").strip()
        if not reason:
            raise ValidationError("Give a reason for cancelling the order.")
        locked_order.status = "cancelled"
        locked_order.notes = f"{locked_order.notes}\nCancelled by {user}: {reason}".strip()
        locked_order.save(update_fields=["status", "notes", "updated_at"])


    # ------------------------------------------------------------------ validation

    def _relation_belongs_to_tenant(self, field_name):
        relation_id = getattr(self, f"{field_name}_id", None)
        if not self.tenant_id or not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def clean(self):
        """Tenant guards, and nothing keyed on a field the form does not carry.

        Deliberately NOT checked here, and the reasons matter:

        * ``impact_snapshot`` — a malformed blob would have been a ``ValidationError`` keyed on
          a field that is ``editable=False`` and off the form, which Django routes through
          ``add_error(None, …)``: a ``ValueError``, and a 500 on every create and edit. Its
          shape is normalised in ``save()`` instead, which is a data fix rather than a form
          error, and every reader already tolerates a bad blob.
        * ``status`` — workflow-owned and off the form, same trap.
        * the order's amendability — a *form* concern (the create form narrows its dropdown and
          re-checks on submit) and a *race* concern (it can change between render and submit).
          ``apply()`` re-checks it in the method, which is the only check that cannot be
          bypassed by posting directly.
        """
        super().clean()
        if not self.tenant_id:
            return
        # An amendment against another workspace's order is the one combination that would let
        # a clerk apply a change order to a customer they cannot otherwise see.
        if not self._relation_belongs_to_tenant("sales_order"):
            raise ValidationError({"sales_order": "The sales order must belong to this workspace."})
        if not self._relation_belongs_to_tenant("document"):
            raise ValidationError({"document": "The document must belong to this workspace."})

    def save(self, *args, **kwargs):
        # The one place a malformed snapshot is repaired. Doing it here rather than in
        # ``clean()`` keeps a field the form does not have out of the validation path (see the
        # ``clean()`` docstring), while still guaranteeing every reader gets the mapping
        # ``parsed_impact`` promises.
        if not isinstance(self.impact_snapshot, dict):
            self.impact_snapshot = {}


class OrderAmendmentLine(models.Model):
    """One proposed line change inside an amendment.

    **Tenant-less**, like every other order-line child in the repo (``scm.SalesOrderLine``,
    ``scm.PurchaseOrderLine``, ``scm.GoodsReceiptLine``): it is reached through ``amendment``
    and the tenant is one hop away via ``amendment.tenant``. It therefore takes **no**
    ``NUMBER_PREFIX`` and has no ``number`` column at all.

    ``sales_order_line`` is nullable and ``SET_NULL`` for one structural reason rather than a
    convenience: an ``add_line`` amendment proposes a line that **does not exist yet**, so
    there is no original to point at. A non-null column or ``PROTECT`` would make the most
    ordinary kind of amendment unrepresentable.

    ``operation`` is what gives ``new_quantity`` / ``new_unit_price`` their meaning:

    * ``add`` — no original line; the pair IS the new line.
    * ``update`` — an original line; either figure may move, and a blank one means "leave it".
    * ``remove`` — an original line, and the pair must stay blank: a removal that also carries
      a quantity is two instructions in one row, and nobody can tell which one won.
    """

    OPERATION_CHOICES = [
        ("add", "Add"),
        ("update", "Update"),
        ("remove", "Remove"),
    ]

    amendment = models.ForeignKey(OrderAmendment, on_delete=models.CASCADE, related_name="lines")
    # SET_NULL, not CASCADE: deleting the order line that an amendment proposed to change
    # retires the proposal's TARGET, it does not retract the proposal. The amendment and its
    # frozen impact snapshot are the record; losing them on an SCM delete would be the wrong
    # way for that record to end.
    sales_order_line = models.ForeignKey("scm.SalesOrderLine", on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name="order_amendment_lines")
    operation = models.CharField(max_length=8, choices=OPERATION_CHOICES, default="update")
    new_quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                       validators=[MinValueValidator(Decimal("0.0001"))])
    new_unit_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(ZERO)])
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def is_addition(self):
        return self.operation == "add"

    def clean(self):
        """The three operation rules — all on ``NON_FIELD_ERRORS``, and that is not a style choice.

        This model's form is ``OrderAmendmentLineForm``, whose ``Meta.fields`` are
        ``[sales_order_line, operation, new_quantity, new_unit_price, note]``. It does **not**
        carry ``amendment`` (set by the parent view), nor ``created_at`` / ``updated_at``. A
        ``ValidationError`` keyed on any of those routes through Django's ``add_error(None, …)``,
        which raises ``ValueError`` for a key the form does not have — a 500 on every create
        and edit, and a *data-dependent* one, so the same dropdown would 500 for one amendment
        and quietly save for another depending on invisible prior state. That is the 0.20
        close-out finding, and it is why every message here is non-field.
        """
        super().clean()
        messages = []
        if self.operation == "add":
            if self.sales_order_line_id:
                messages.append(
                    "An Add line has no original line to point at — leave the order line blank."
                )
        elif not self.sales_order_line_id:
            messages.append(
                f"A {self.get_operation_display()} line must name the order line it changes."
            )
        if self.operation == "remove":
            if self.new_quantity is not None:
                messages.append("A Remove line carries no new quantity — delete the line instead.")
            if self.new_unit_price is not None:
                messages.append("A Remove line carries no new unit price — delete the line instead.")
        if messages:
            raise ValidationError({NON_FIELD_ERRORS: messages})

    def __str__(self):
        if self.operation == "add":
            return f"Add {self.new_quantity or '?'} @ {self.new_unit_price or ZERO}"
        if self.sales_order_line_id:
            return f"{self.get_operation_display()} line {self.sales_order_line_id}"
        return f"{self.get_operation_display()} line"
