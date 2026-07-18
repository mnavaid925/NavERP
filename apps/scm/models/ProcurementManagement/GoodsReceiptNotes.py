"""SCM 4.1 Procurement Management — GoodsReceiptNotes models.

Realizes the "Invoice Reconciliation" bullet: the THREE-WAY MATCH between what we ordered
(``scm.PurchaseOrder``), what we received (this GRN), and what the vendor billed us
(``accounting.Bill`` — the real AP bill from Module 2; we deliberately do not invent a parallel
"VendorInvoice" model).

There is no ``StockMove`` posting here: ``core.StockMove`` does not exist yet (it lands with
Module 5 Inventory, lesson L28). When it does, ``mark_received`` is the hook that should post the
inventory effect inside ``transaction.atomic()``.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class GoodsReceiptNote(TenantNumbered):
    """A receipt of goods against a purchase order [GRN-]."""

    NUMBER_PREFIX = "GRN"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft",)

    MATCH_STATUS_CHOICES = [
        ("not_matched", "Not Matched"),
        ("matched", "Matched"),
        ("price_variance", "Price Variance"),
        ("quantity_variance", "Quantity Variance"),
        ("over_received", "Over Received"),
    ]
    # A vendor bill may differ from the receipt's value by this much before it is a variance.
    PRICE_TOLERANCE_PCT = Decimal("2")

    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.PROTECT, related_name="receipts")
    # 4.4 WMS: where the goods physically land on arrival. Booking the receipt posts the inbound
    # StockMove into this location; 4.4 putaway then moves it from here to its final bin.
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="goods_receipts",
                                 help_text="Receiving / staging location the goods land in")
    receipt_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    delivery_note_ref = models.CharField(max_length=64, blank=True, help_text="The vendor's delivery-note number")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_goods_receipts")

    # --- three-way match -----------------------------------------------------------------
    bill = models.ForeignKey("accounting.Bill", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="scm_goods_receipts",
                             help_text="The vendor bill this receipt is matched against")
    match_status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES, default="not_matched",
                                    editable=False)
    match_notes = models.TextField(blank=True, editable=False)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-receipt_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_grn_tenant_status_idx"),
            models.Index(fields=["tenant", "match_status"], name="scm_grn_tenant_match_idx"),
            # 4.2 SupplierScorecard.recompute_from_signals filters received receipts by date range.
            models.Index(fields=["tenant", "receipt_date"], name="scm_grn_tenant_date_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def received_value(self, lines=None):
        """What this receipt accepted, priced at the PO's agreed unit prices. NET of tax.

        ``lines`` lets a caller that has already fetched the rows (the detail view, and
        recompute_match below) hand them in rather than pay for the identical query twice.
        """
        if lines is None:
            lines = self.lines.select_related("po_line")
        total = ZERO
        for line in lines:
            if line.po_line_id:
                total += (line.quantity_received or ZERO) * (line.po_line.unit_price or ZERO)
        return total

    def billed_value(self):
        """What the vendor billed, NET of tax — the like-for-like counterpart to received_value().

        Uses the bill's ex-tax subtotal on purpose: a three-way match is about the goods value.
        Tax is a separate reconciliation (rates legitimately differ from the PO's estimate), and
        folding it in here would flag every taxed bill as a price variance.
        """
        if not self.bill_id:
            return ZERO
        return self.bill.subtotal or ZERO

    def recompute_match(self, save=True, received_map=None):
        """Derive ``match_status`` from PO vs. GRN vs. Bill.

        Order matters: an over-receipt is reported even when the money happens to line up, because
        it is the more serious finding — we accepted goods we never ordered.

        ``received_map`` is ``{po_line_id: accepted quantity}`` from
        ``PurchaseOrder.received_by_line()``. It is identical for every receipt on the order, so
        ``rematch_receipts()`` builds it once and passes it in; deriving it per line here (twice,
        for over and short) is what made the receipt-booking path O(N x R) queries.
        """
        notes = []
        if self.status == "cancelled":
            status = "not_matched"
            notes.append("Receipt is cancelled.")
        else:
            lines = list(self.lines.select_related("po_line"))
            if received_map is None:
                received_map = self.purchase_order.received_by_line()
            over, short = [], []
            for line in lines:
                if not line.po_line_id:
                    continue
                received = received_map.get(line.po_line_id, ZERO)
                if received > line.po_line.quantity:
                    over.append(line)
                elif received < line.po_line.quantity:
                    short.append(line)
            if over:
                status = "over_received"
                notes.append(
                    f"{len(over)} line(s) received beyond the ordered quantity."
                )
            elif not self.bill_id:
                status = "not_matched"
                notes.append("No vendor bill linked yet.")
            else:
                expected = self.received_value(lines=lines)
                # Match on the NET goods value: received_value() is ex-tax (quantity x the PO's
                # agreed unit price), so it must be compared against the bill's ex-tax subtotal.
                # Comparing it to bill.total would read the tax rate itself as a price variance.
                billed = self.billed_value()
                if expected > ZERO:
                    variance_pct = abs(billed - expected) / expected * 100
                else:
                    variance_pct = ZERO if billed == ZERO else Decimal("100")
                if variance_pct > self.PRICE_TOLERANCE_PCT:
                    status = "price_variance"
                    notes.append(
                        f"Billed {billed} against a received value of {expected} "
                        f"({variance_pct:.2f}% over the {self.PRICE_TOLERANCE_PCT}% tolerance)."
                    )
                elif short:
                    status = "quantity_variance"
                    notes.append(f"{len(short)} line(s) not yet received in full.")
                else:
                    status = "matched"
                    notes.append("PO, receipt and bill agree within tolerance.")
        self.match_status = status
        self.match_notes = " ".join(notes)
        if save:
            self.save(update_fields=["match_status", "match_notes", "updated_at"])
        return status

    def __str__(self):
        return f"{self.number or 'GRN'} · {self.purchase_order_id}"


class GoodsReceiptLine(models.Model):
    """Quantity accepted (and rejected) against one purchase-order line."""

    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.CASCADE, related_name="lines")
    po_line = models.ForeignKey("scm.PurchaseOrderLine", on_delete=models.PROTECT, related_name="receipt_lines")
    quantity_received = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)],
                                            help_text="Quantity accepted into stock")
    quantity_rejected = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)],
                                            help_text="Quantity refused (damaged / out of spec)")
    rejection_reason = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]

    def clean(self):
        super().clean()
        if self.quantity_rejected and self.quantity_rejected > 0 and not self.rejection_reason:
            raise ValidationError({"rejection_reason": "Give a reason when rejecting a quantity."})

    def __str__(self):
        return f"{self.po_line_id} ×{self.quantity_received}"
