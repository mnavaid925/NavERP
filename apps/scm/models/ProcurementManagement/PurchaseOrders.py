"""SCM 4.1 Procurement Management — PurchaseOrders models.

This is the CANONICAL purchase order. Note that ``crm.PurchaseOrder`` also exists (CRM 1.12): that
one is a deliberately lightweight "quick order" built before any procurement module existed — free-text
items, no currency, no approval workflow. The two coexist intentionally (separate app_labels, separate
tables, separate number sequences); this is not a duplication bug. Module 6 (Procurement) is expected
to EXTEND this model by FK for strategic sourcing rather than declaring a third one.

Received quantities are DERIVED from goods-receipt lines, never stored on the order — the spine rule
that on-hand/received quantities are aggregates, not editable fields.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class PurchaseOrder(TenantNumbered):
    """A purchase order issued to a vendor [PO-]. Totals are recomputed from lines."""

    NUMBER_PREFIX = "PO"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("sent", "Sent"),
        ("acknowledged", "Acknowledged"),
        ("partially_received", "Partially Received"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
        ("closed", "Closed"),
    ]
    # Once dispatched to the vendor the order is a commitment — edits go through an amendment.
    EDITABLE_STATUSES = ("draft", "pending_approval")
    # Statuses from which a receipt may be booked.
    RECEIVABLE_STATUSES = ("approved", "sent", "acknowledged", "partially_received")
    # Terminal — no further transitions.
    CLOSED_STATUSES = ("cancelled", "closed")

    vendor = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="scm_purchase_orders")
    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="purchase_orders")
    quote = models.ForeignKey("scm.RFQQuote", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="purchase_orders", help_text="Awarded quote this PO came from")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_purchase_orders")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="scm_purchase_orders")
    order_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    ship_to = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="scm_purchase_orders", help_text="Delivering to which site/unit")
    delivery_address = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)

    # Amendment trail: bumped on every post-approval change; the field-level diff lives in AuditLog.
    version = models.PositiveIntegerField(default=1, editable=False)
    amendment_reason = models.TextField(blank=True, editable=False)

    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_purchase_orders_approved", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)

    # Vendor acknowledgement. Recorded by STAFF here — there is no vendor login in this pass
    # (lesson L32: a staff sidebar bullet must never point at a login-gated portal page). A real
    # supplier self-service portal is deferred; these fields are what it would write.
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledgement_note = models.CharField(max_length=255, blank=True, editable=False)
    promised_ship_date = models.DateField(null=True, blank=True, editable=False)

    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancellation_reason = models.TextField(blank=True, editable=False)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_po_tenant_status_idx"),
            models.Index(fields=["tenant", "order_date"], name="scm_po_tenant_date_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    def recalc_totals(self, save=True):
        rows = list(self.lines.all())
        subtotal = sum((r.line_total for r in rows), ZERO)
        tax = sum(((r.line_total * (r.tax_rate_pct or ZERO) / 100) for r in rows), ZERO)
        self.subtotal, self.tax_total, self.total = subtotal, tax, subtotal + tax
        if save:
            self.save(update_fields=["subtotal", "tax_total", "total", "updated_at"])

    def rematch_receipts(self):
        """Re-derive the three-way match on EVERY receipt against this order.

        A receipt's verdict depends on ``po_line.received_quantity()``, which aggregates across all
        of the order's receipts — so booking or cancelling one receipt can silently invalidate a
        sibling's stored verdict (e.g. an earlier receipt still reading "Quantity Variance" after a
        later one pushed the line into over-receipt). Re-matching the whole set keeps them honest.
        """
        for receipt in self.receipts.all():
            receipt.recompute_match()

    def recompute_receipt_status(self):
        """Derive sent/partially_received/received from booked receipt lines.

        Only moves within the receiving part of the lifecycle — never resurrects a cancelled or
        closed order, and never downgrades an order that was never dispatched.
        """
        if self.status in self.CLOSED_STATUSES or self.status in self.EDITABLE_STATUSES:
            return
        rows = list(self.lines.all())
        if not rows:
            return
        fully = all(r.received_quantity() >= r.quantity for r in rows)
        any_received = any(r.received_quantity() > ZERO for r in rows)
        if fully:
            new = "received"
        elif any_received:
            new = "partially_received"
        else:
            new = "acknowledged" if self.acknowledged_at else "sent"
        if new != self.status:
            self.status = new
            self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"{self.number or 'PO'} · {self.vendor}"


class PurchaseOrderLine(models.Model):
    """One ordered item. ``line_total`` is derived; received quantity is aggregated from GRN lines."""

    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.CASCADE, related_name="lines")
    item_description = models.CharField(max_length=255)
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField(max_length=32, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)])
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                       validators=[MinValueValidator(ZERO)])
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="scm_purchase_order_lines")

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or ZERO) * (self.unit_price or ZERO)
        super().save(*args, **kwargs)

    def received_quantity(self):
        """Total accepted quantity booked against this line across every non-cancelled receipt."""
        return self.receipt_lines.exclude(goods_receipt__status="cancelled").aggregate(
            s=Sum("quantity_received"))["s"] or ZERO

    def outstanding_quantity(self):
        return (self.quantity or ZERO) - self.received_quantity()

    def __str__(self):
        return f"{self.item_description} ×{self.quantity}"
