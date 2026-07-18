"""SCM 4.5 Order Management System — SalesOrder + SalesOrderLine models.

**apps/scm OWNS the sales order.** `NavERP-ERD.md` nominally assigns `SalesOrder` to Modules 1/8/9,
but Module 1 (CRM) is fully built across all twelve of its sub-modules and deliberately stopped at
`Lead → Opportunity → Quote` — `crm.Quote.quote_accept()` flips a status and creates nothing
downstream. Modules 8 and 9 do not exist. Under the ships-first rule (L28/L29/L36/L37) 4.5 builds it
now and owns it; Module 8.6 "Order Management" is a DIFFERENT, later feature set (commercial
amend/cancel with impact analysis, revenue recognition, reorder) that will FK INTO this order rather
than declare a second one. Unlike the `crm.PurchaseOrder` / `scm.PurchaseOrder` pair — two versions
that coexist on purpose — there is no order-shaped model in CRM to collide with here, so this is
clean single ownership, closer to how 4.3 took `Item`/`Location`/`StockMove`.

Quantities on a line are DERIVED from its allocations, never stored: `quantity_allocated()` and
`quantity_backordered()` aggregate over `SalesOrderAllocation`, the same spine rule that keeps
on-hand an aggregate over `StockMove`.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SalesOrder(TenantNumbered):
    """A customer order [SO-]. Totals are recomputed from lines; status is action-driven."""

    NUMBER_PREFIX = "SO"

    SOURCE_CHANNEL_CHOICES = [
        ("manual", "Manual"),
        ("web", "Web"),
        ("marketplace", "Marketplace"),
        ("edi", "EDI"),
        ("api", "API"),
        ("phone", "Phone"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("on_hold", "On Hold"),
        ("allocated", "Allocated"),
        ("partially_fulfilled", "Partially Fulfilled"),
        ("fulfilled", "Fulfilled"),
        ("invoiced", "Invoiced"),
        ("cancelled", "Cancelled"),
        ("closed", "Closed"),
    ]
    # Once submitted the order is a live customer-facing commitment. Mirrors PurchaseOrder treating
    # `sent` as locked. There is deliberately NO amendment flow here — amend/cancel with impact
    # analysis is Module 8.6's job, not something to half-build now.
    EDITABLE_STATUSES = ("draft",)
    # Statuses `recompute_allocation_status()` is allowed to move between. Anything else — a
    # fulfilled, invoiced, cancelled, closed, draft or held order — is left alone even if an
    # allocation changes underneath it (mirrors PurchaseOrder.recompute_receipt_status's guard).
    ALLOCATABLE_STATUSES = ("submitted", "allocated", "partially_fulfilled")
    CLOSED_STATUSES = ("cancelled", "closed")

    customer = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="sales_orders")
    ship_to_address = models.ForeignKey("core.Address", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="sales_orders_shipped")
    source_channel = models.CharField(max_length=12, choices=SOURCE_CHANNEL_CHOICES, default="manual",
                                      help_text="Where the order came in from")
    # Set by salesorder_create_from_quote, not hand-picked on the general form.
    source_quote = models.ForeignKey("crm.Quote", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="sales_orders")
    order_date = models.DateField(null=True, blank=True)
    requested_date = models.DateField(null=True, blank=True,
                                      help_text="The date the customer asked for")
    # Set ONCE, the first time the order reaches `allocated` — a promise made from what was actually
    # reserved, not a speculative forecast. editable=False keeps it off the form (L22).
    promised_date = models.DateField(null=True, blank=True, editable=False)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_sales_orders")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="scm_sales_orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", editable=False)
    # The three hold fields are system-set by salesorder_submit's credit/fraud evaluation and
    # cleared by salesorder_release_hold — never typed by a user, so they stay off the form.
    credit_hold = models.BooleanField(default=False, editable=False)
    fraud_flag = models.BooleanField(default=False, editable=False)
    hold_reason = models.TextField(blank=True, editable=False)
    # Notification DATA hooks only — this pass stamps when each notification would have gone out and
    # dispatches nothing. Same hand-off posture as 4.4's YardVisit.carrier_name and
    # PickTask.tracking_ref: record the fact, leave the integration to the module that owns it.
    confirmation_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    shipped_notification_at = models.DateTimeField(null=True, blank=True, editable=False)
    delivered_notification_at = models.DateTimeField(null=True, blank=True, editable=False)
    # A plain user-editable field. Linking the invoice does NOT flip the status — that is the
    # separate salesorder_mark_invoiced action, so setting an FK never silently advances workflow.
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="sales_orders")
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_so_tnt_status_idx"),
            models.Index(fields=["tenant", "order_date"], name="scm_so_tnt_date_idx"),
        ]

    def recalc_totals(self, save=True):
        """Sum the lines in PYTHON, not with an F() expression.

        `F("quantity_ordered") * F("unit_price") * (1 - F("discount_pct") / 100)` integer-divides on
        SQLite and silently drops every per-line discount and tax — the same trap `crm.Quote`'s own
        docstring warns about. Decimal arithmetic in a loop is correct on every backend and these
        documents have tens of lines, not thousands.
        """
        subtotal, tax = ZERO, ZERO
        for line in self.lines.all():
            subtotal += line.line_subtotal
            tax += line.line_tax
        self.subtotal, self.tax_total, self.total = subtotal, tax, subtotal + tax
        if save:
            self.save(update_fields=["subtotal", "tax_total", "total", "updated_at"])
        return self.total

    def recompute_allocation_status(self):
        """Derive submitted / partially_fulfilled / allocated from what the lines have reserved.

        `partially_fulfilled` here means SOME quantity is reserved and the remainder is backordered —
        it does NOT mean partially shipped. This sub-module never tracks physical shipment; that is
        4.4's pick/pack and, later, 4.6's carrier work.

        Terminal and pre-submit states are left alone: an order that is fulfilled, invoiced,
        cancelled, closed, still draft, or on hold must not be dragged backwards by an allocation
        edit (mirrors PurchaseOrder.recompute_receipt_status).
        """
        if self.status not in self.ALLOCATABLE_STATUSES:
            return self.status
        # ONE grouped query for every line's allocated total. The obvious version — looping
        # quantity_allocated()/quantity_backordered() — costs an aggregate per line, and
        # quantity_backordered() calls quantity_allocated() again, so it re-derives the same figure
        # twice. This runs after EVERY allocation create/edit/cancel/delete, not once per page, so
        # that cost lands on a button click. PurchaseOrder.received_by_line() already solved exactly
        # this and its docstring says why — same shape, same fix (perf review).
        lines = list(self.lines.annotate(
            _allocated=Sum("allocations__quantity",
                           filter=~Q(allocations__status="cancelled"))))
        any_allocated = any((l._allocated or ZERO) > ZERO for l in lines)
        fully_covered = bool(lines) and all(
            (l._allocated or ZERO) >= (l.quantity_ordered or ZERO) for l in lines)
        if fully_covered and any_allocated:
            new_status = "allocated"
        elif any_allocated:
            new_status = "partially_fulfilled"
        else:
            new_status = "submitted"
        fields = ["status", "updated_at"]
        self.status = new_status
        # Stamped the first time the order is fully covered, and never moved afterwards — a promise
        # already given to the customer does not silently change when a later edit re-derives it.
        if new_status == "allocated" and self.promised_date is None:
            self.promised_date = timezone.localdate()
            fields.insert(1, "promised_date")
        self.save(update_fields=fields)
        return new_status

    def has_active_allocations(self):
        """True when any line still holds a reserved/released claim. Blocks cancellation.

        Traverses the reverse relation rather than naming SalesOrderAllocation, which lives in a
        sibling module: importing it here at module scope would be a circular import, and importing
        inside the method just to run one query is noise when the ORM can walk it.
        """
        return self.lines.filter(allocations__status__in=("reserved", "released")).exists()

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def is_held(self):
        return self.credit_hold or self.fraud_flag

    def __str__(self):
        who = self.customer.name if self.customer_id else "?"
        return f"{self.number or 'SO'} · {who}"


class SalesOrderLine(models.Model):
    """One ordered item. No tenant FK of its own — reached via ``sales_order.tenant``, matching the
    scm sibling convention (PurchaseOrderLine, RFQLine, GoodsReceiptLine are all tenant-less
    children) rather than crm.QuoteLine's outlier.

    ``item`` is a REAL FK to ``scm.Item``. Procurement's free-text ``item_description``/``sku_hint``
    stand-in (L28) existed only because 4.1 shipped before the item catalog did; 4.5 ships after 4.3,
    so there is nothing to work around.
    """

    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="lines")
    # Nullable ONLY so a quote conversion can land: `crm.QuoteLine.product` is a CRM Product, a
    # different table from `scm.Item` with no mapping between them, and guessing one by name would
    # quietly attach an order to the wrong stock. A converted line therefore arrives with the
    # quote's description and no item, and `salesorder_submit` REFUSES to submit while any line is
    # still unmapped — so the gap is a visible to-do on a draft, never something that ships.
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, null=True, blank=True,
                             related_name="sales_order_lines")
    description = models.CharField(max_length=255, blank=True,
                                   help_text="Optional override of the item name on this order")
    quantity_ordered = models.DecimalField(max_digits=14, decimal_places=4,
                                           validators=[MinValueValidator(Decimal("0.0001"))])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)])
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                       validators=[MinValueValidator(0), MaxValueValidator(100)])
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        ordering = ["id"]

    # Properties, never stored — same formula as crm.QuoteLine.
    @property
    def line_subtotal(self):
        gross = (self.quantity_ordered or ZERO) * (self.unit_price or ZERO)
        return gross * (Decimal("1") - (self.discount_pct or ZERO) / Decimal("100"))

    @property
    def line_tax(self):
        return self.line_subtotal * (self.tax_pct or ZERO) / Decimal("100")

    @property
    def line_total(self):
        return self.line_subtotal + self.line_tax

    def quantity_allocated(self):
        """How much of this line is spoken for. Cancelled claims release their hold and stop
        counting; released ones still count — released means "sent to the floor", not "gone"."""
        return self.allocations.exclude(status="cancelled").aggregate(s=Sum("quantity"))["s"] or ZERO

    def quantity_backordered(self):
        remaining = (self.quantity_ordered or ZERO) - self.quantity_allocated()
        return remaining if remaining > ZERO else ZERO

    @property
    def is_backordered(self):
        return self.quantity_backordered() > ZERO

    @property
    def is_unmapped(self):
        """A converted-from-quote line that still has no stock item picked."""
        return self.item_id is None

    def __str__(self):
        sku = self.item.sku if self.item_id else (self.description or "unmapped")
        return f"{sku} ×{self.quantity_ordered}"
