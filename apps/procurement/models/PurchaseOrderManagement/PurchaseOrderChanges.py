"""Procurement 6.10 Purchase Order Management — PurchaseOrderChange models.

**PO Change Order Management** bullet: a process for modifying quantity, price or delivery
date on an ACTIVE purchase order. The ``scm.PurchaseOrder`` spine deliberately allows IN-PLACE
editing only while an order is still a draft / pending approval — once dispatched (sent /
acknowledged / partially received) it is a commitment to the vendor, and a silent edit would
undermine whatever version the vendor acknowledged. This model is the gated alternative,
mirroring 6.2's RequisitionAmendment exactly: any workspace member FILES a proposed change
(amend header/lines, or cancel the order), a tenant admin APPROVES or rejects it, and ONLY the
approve action touches ``scm.PurchaseOrder`` — inside one transaction under a row lock on the
order, with the decision recorded on the change row and in ``core.AuditLog``.

The proposed line changes live on ``PurchaseOrderChangeLine`` rows so the diff is reviewable
BEFORE it happens; applying is deterministic (add/update/remove) rather than free-text.
Approval bumps the spine's ``version`` and stamps ``amendment_reason`` so the amendment trail
the SCM module started keeps a continuous story.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403


class PurchaseOrderChange(TenantNumbered):
    """A requested change (or cancellation) to an active purchase order [PCO-].

    Lifecycle: ``pending`` -> ``approved`` (applies the change to the order immediately,
    atomically, bumping its version) or ``rejected``. The decision is final and recorded;
    there is no un-apply — that is what makes the workflow safe to gate with a single yes/no.
    """

    NUMBER_PREFIX = "PCO"

    CHANGE_TYPES = [
        ("amend", "Change details"),
        ("cancel", "Cancel order"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    # Order statuses a change order may target. Drafts / pending approvals can be edited in
    # place through the spine's own paths, and received/cancelled/closed are terminal — the
    # bullet's "active PO" is precisely the dispatched-not-yet-complete window.
    CHANGEABLE_STATUSES = ("sent", "acknowledged", "partially_received")

    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.PROTECT,
                                       related_name="procurement_changes",
                                       help_text="The purchase order this change proposes to alter")
    change_type = models.CharField(max_length=8, choices=CHANGE_TYPES, default="amend")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="pending")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="procurement_po_changes_requested",
                                     editable=False)
    reason = models.TextField(help_text="Why this change / cancellation is needed")

    # -- proposed header changes (amend type; blank = leave unchanged) --------------------------
    new_expected_date = models.DateField(null=True, blank=True,
                                         help_text="Proposed new expected delivery date")
    new_notes = models.TextField(blank=True,
                                 help_text="Proposed replacement notes text")

    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True,
                                   related_name="procurement_po_changes_decided", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, editable=False)
    applied_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_pco_tenant_status_idx"),
            models.Index(fields=["tenant", "change_type"], name="prc_pco_tenant_type_idx"),
        ]

    @property
    def is_pending(self):
        return self.status == "pending"

    @property
    def is_cancel(self):
        return self.change_type == "cancel"

    @classmethod
    def has_open_for(cls, order):
        """True while ANY change order on this PO is still undecided — one open change at a
        time keeps 'what does the order look like if approved?' answerable."""
        return order.procurement_changes.filter(status="pending").exists()

    def clean(self):
        # Cancel changes carry no proposed changes by definition.
        if self.is_cancel:
            for field in ("new_expected_date", "new_notes"):
                if getattr(self, field):
                    raise ValidationError({field: "A cancellation does not carry proposed changes."})

    def __str__(self):
        return f"{self.number or 'PCO'} · {self.get_change_type_display()} · {self.purchase_order_id}"

    # -- apply ---------------------------------------------------------------------------------

    def apply(self, decider, note=""):
        """Approve AND apply in one atomic step. Returns the summary string of what changed.

        Caller contract (enforced in the view): status must be ``pending``, the order must
        still be in CHANGEABLE_STATUSES, and this runs inside ``transaction.atomic()`` with a
        row lock held on the purchase order. A lost line target (the order changed between
        filing and deciding) is skipped and REPORTED rather than silently ignored or fatal to
        the whole batch — mirroring RequisitionAmendment.apply().
        """
        now = timezone.now()
        summary = []
        order = self.purchase_order

        if self.is_cancel:
            order.status = "cancelled"
            order.cancelled_at = now
            order.cancellation_reason = f"Cancelled via change order {self.number}: {self.reason[:1800]}"
            order.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
            summary.append("order cancelled")
        else:
            header_bits = []
            if self.new_expected_date:
                order.expected_date = self.new_expected_date
                header_bits.append(f"expected-date -> {self.new_expected_date:%Y-%m-%d}")
            if self.new_notes:
                order.notes = self.new_notes
                header_bits.append("notes replaced")

            line_bits = []
            for line in self.lines.select_related("target_line"):
                outcome = line.apply_to_order()
                if outcome:
                    line_bits.append(outcome)

            # Derived totals are ALWAYS recomputed from the (possibly altered) lines.
            order.recalc_totals()

            # Post-dispatch change => the spine's amendment trail moves: version bumps and the
            # reason lands where SCM's own amend verb stamps its edits.
            order.version = (order.version or 1) + 1
            order.amendment_reason = f"Change order {self.number}: {self.reason[:1800]}"

            update_fields = ["subtotal", "tax_total", "total", "version", "amendment_reason",
                             "updated_at"]
            if header_bits:
                update_fields += ["expected_date", "notes"]
            order.save(update_fields=update_fields)

            # Quantity reductions can move an order's receipt state (e.g. shrinking below what
            # has already arrived makes it effectively fully received) — re-derive honestly
            # instead of leaving the lifecycle stale behind our own edit.
            order.recompute_receipt_status(received_map=order.received_by_line())

            summary.extend(line_bits + header_bits)

        self.status = "approved"
        self.decided_by = decider
        self.decided_at = now
        self.applied_at = now
        self.decision_note = (note or "").strip()[:2000]
        self.save(update_fields=["status", "decided_by", "decided_at", "applied_at",
                                 "decision_note", "updated_at"])
        return "; ".join(summary) or "no changes were required"


class PurchaseOrderChangeLine(models.Model):
    """One PROPOSED line change on an amend-type purchase order change.

    ``action`` says what happens on approval: ``add`` creates a new order line from the
    proposed values; ``update`` overwrites the target line's quantity/price/tax rate (blank
    proposal = keep current value); ``remove`` deletes the target line. ``target_line`` is
    SET_NULL, not PROTECT, because the order's lines stay editable upstream while this pends —
    apply_to_order() reports a lost target instead of blocking an unrelated edit with a
    database error. Lines that goods have ALREADY been booked against are protected from
    removal (and from shrinkage below the received quantity) at apply time.
    """

    ACTION_CHOICES = [
        ("add", "Add line"),
        ("update", "Update line"),
        ("remove", "Remove line"),
    ]

    change = models.ForeignKey("procurement.PurchaseOrderChange", on_delete=models.CASCADE,
                               related_name="lines")
    target_line = models.ForeignKey("scm.PurchaseOrderLine", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="change_lines",
                                    help_text="Which existing line this changes (blank = a new line)")
    action = models.CharField(max_length=6, choices=ACTION_CHOICES, default="update")
    item_description = models.CharField(max_length=255, blank=True,
                                        help_text="Required when adding a line")
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField(max_length=32, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("0.0001"))],
                                   help_text="Blank on update = keep the current quantity")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(ZERO)],
                                     help_text="Blank on update = keep the current price")
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                       validators=[MinValueValidator(ZERO)],
                                       help_text="Blank on update = keep the current tax rate")

    class Meta:
        ordering = ["id"]

    def clean(self):
        if self.action in ("update", "remove") and self.target_line_id is None:
            raise ValidationError({"target_line": f"A '{self.action}' needs an existing line."})
        if self.action == "add":
            if self.target_line_id is not None:
                raise ValidationError({"action": "Adding a line cannot target an existing line."})
            if not (self.item_description or "").strip():
                raise ValidationError({"item_description": "A new line needs a description."})

    def apply_to_order(self):
        """Write THIS proposed change onto the parent purchase order. Returns a human summary,
        or a ``"not applied — …"`` note when the target vanished (or booked goods make the
        change unsafe) before approval. Never raises for a lost target: one stale row must not
        abort the whole batch."""
        from apps.scm.models import PurchaseOrderLine  # deferred import, see RequisitionAmendment

        if self.action == "add":
            PurchaseOrderLine.objects.create(
                purchase_order=self.change.purchase_order,
                item_description=self.item_description,
                sku_hint=self.sku_hint or "",
                uom_hint=self.uom_hint or "",
                quantity=self.quantity or Decimal("1"),
                unit_price=self.unit_price or ZERO,
                tax_rate_pct=self.tax_rate_pct or ZERO,
            )
            return f"added '{(self.item_description or '')[:60]}'"
        if self.target_line_id is None:
            return f"'{self.get_action_display()}' not applied — target line no longer exists"
        target = self.target_line
        if self.action == "remove":
            received = target.received_quantity()
            if received > ZERO:
                return (f"not applied — '{target.item_description[:60]}' already has "
                        f"{received} received; cancel the order instead")
            desc = target.item_description[:60]
            target.delete()
            return f"removed '{desc}'"
        # update: only the fields actually proposed move — blank means keep.
        changed = []
        if self.quantity is not None:
            received = target.received_quantity()
            if self.quantity < received:
                return (f"not applied — '{target.item_description[:60]}' already has "
                        f"{received} received; ordered quantity cannot drop below that")
            target.quantity = self.quantity
            changed.append("qty")
        if self.unit_price is not None:
            target.unit_price = self.unit_price
            changed.append("price")
        if self.tax_rate_pct is not None:
            target.tax_rate_pct = self.tax_rate_pct
            changed.append("tax")
        if changed:
            target.save()
            return f"updated '{target.item_description[:60]}' ({'+'.join(changed)})"
        return ""
