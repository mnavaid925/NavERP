"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoiceLine.

One line of a supplier's claim: what they say they delivered, at what price, against which
ordered line and which receipt, and where it posts in the ledger.

**This model is a PLAIN CHILD** — no ``tenant`` column of its own and no ``number``. It is
scoped through ``invoice`` the way ``scm.GoodsReceiptLine`` is scoped through ``goods_receipt``
and ``procurement.AsnLine`` through ``asn``: every queryset in this app filters
``invoice__tenant=`` and never the child directly.

**Nothing here is stored that can be derived.** ``line_total`` is recomputed in ``save()`` and
the header's ``subtotal`` / ``tax_total`` / ``total`` follow it through
``SupplierInvoice.recalc_totals()``. ``cumulative_invoiced_qty`` and
``cumulative_received_qty`` are PROPERTIES over the same aggregates the match engine uses — a
stored counter drifts the first time a receipt is cancelled or an invoice is reversed, and the
correct answer is one query away.

**Import discipline.** ``SupplierInvoice`` is imported LAZILY inside the two cumulative
properties: ``SupplierInvoices.py`` imports THIS module at module level (it needs
``SupplierInvoiceLine`` for its own aggregates), so a module-level import back the other way is a
star-import cycle at URLconf import. Deferring it one call keeps the dependency one-directional.
"""
from decimal import Decimal, InvalidOperation

from apps.procurement.models._base import *  # noqa: F401,F403

#: Column-width ceilings, checked in ``clean()``. A hand-fed ``1e400`` parses as a Decimal and
#: then dies inside the driver, so magnitude is checked BEFORE anything is written.
_QUANTITY_CEILING = Decimal(10) ** 10        # DecimalField(14, 4)
_UNIT_PRICE_CEILING = Decimal(10) ** 12      # DecimalField(14, 2)


def _finite(value):
    """``value`` as a finite ``Decimal``, or ``None`` (L35/L11).

    ``Decimal("nan")`` and ``Decimal("Infinity")`` both PARSE and then raise on the COMPARISON,
    so finiteness is tested before anything else touches the figure.
    """
    try:
        number = Decimal(value if value is not None else ZERO)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    return number if number.is_finite() else None


def _as_decimal(value):
    """``value`` as a usable ``Decimal`` — ``ZERO`` for anything unusable.

    Every figure a property multiplies goes through here: a NULL or a hand-fed string must not
    turn a derived money column into a TypeError.
    """
    number = _finite(value)
    return ZERO if number is None else number


class SupplierInvoiceLine(models.Model):
    """One invoiced line — what the supplier claims, and what we accept of it.

    ``matched_qty`` is written ONLY by ``SupplierInvoice.run_match()``: it is how much of the
    invoiced quantity survived the three-way match, never more than arrived, never more than
    ordered, never more than was invoiced.
    """

    invoice = models.ForeignKey("procurement.SupplierInvoice", on_delete=models.CASCADE,
                                related_name="lines")
    # scm.PurchaseOrderLine and scm.GoodsReceiptLine are plain models with NO tenant column —
    # they are narrowed through their own headers (purchase_order__tenant / goods_receipt__tenant)
    # in the form, and re-checked against the invoice in clean().
    po_line = models.ForeignKey("scm.PurchaseOrderLine", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="procurement_invoice_lines")
    receipt_line = models.ForeignKey("scm.GoodsReceiptLine", on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="procurement_invoice_lines")
    #: Optional on purpose: the free-text fallback below is what a keyed-from-paper invoice has.
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="procurement_invoice_lines")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="procurement_invoice_lines")
    tax_code = models.ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_invoice_lines")

    #: Mirrored from the PO line when blank (the ``AsnLine.save()`` shape) — the supplier's own
    #: wording is what an AP clerk has to match against the paper.
    description = models.CharField(max_length=255, blank=True)
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField(max_length=32, blank=True)

    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("1"))
    # NO MinValueValidator — a credit memo's lines are legitimately negative.
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO,
                                       validators=[MinValueValidator(ZERO),
                                                   MaxValueValidator(Decimal("100"))])

    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO, editable=False)
    matched_qty = models.DecimalField(max_digits=14, decimal_places=4, default=ZERO, editable=False)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["invoice"], name="prc_sivl_invoice_idx"),
            # Backs the over-invoicing scan (§8.5): every line ever billed against one ordered
            # line, which is exactly the set the cumulative check aggregates.
            models.Index(fields=["po_line"], name="prc_sivl_poline_idx"),
        ]
        verbose_name = "supplier invoice line"

    def __str__(self):
        return f"{self.description or self.sku_hint or 'line'} ×{self.quantity}"

    # -- derived money --------------------------------------------------------------------------

    @property
    def tax_amount(self):
        return q2(_as_decimal(self.line_total) * _as_decimal(self.tax_rate_pct) / Decimal("100"))

    @property
    def gross_total(self):
        return q2(_as_decimal(self.line_total) + self.tax_amount)

    @property
    def is_matched(self):
        return _as_decimal(self.matched_qty) == _as_decimal(self.quantity)

    @property
    def cumulative_invoiced_qty(self):
        """Everything invoiced against this ordered line across every LIVE invoice (derived)."""
        if self.po_line_id is None:
            return ZERO
        # Deferred: SupplierInvoices.py imports this module at module level.
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
        return SupplierInvoice.cumulative_invoiced_qty(self.po_line)

    @property
    def cumulative_received_qty(self):
        """Everything accepted against this ordered line across every LIVE receipt (derived)."""
        if self.po_line_id is None:
            return ZERO
        # Deferred: SupplierInvoices.py imports this module at module level.
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
        return SupplierInvoice.cumulative_received_qty(self.po_line)

    # -- validation -----------------------------------------------------------------------------

    def clean(self):
        errors = {}
        invoice = self.invoice if self.invoice_id else None
        # The line has no tenant of its own — the HEADER's tenant is the line's tenant.
        tenant_id = invoice.tenant_id if invoice is not None else None

        if self.po_line_id and invoice is not None and invoice.purchase_order_id:
            if self.po_line.purchase_order_id != invoice.purchase_order_id:
                # Otherwise a crafted POST staples another order's line onto this invoice and the
                # whole match is then judged against the wrong prices.
                errors["po_line"] = "That line belongs to a different purchase order."

        if self.receipt_line_id and self.po_line_id:
            if self.receipt_line.po_line_id != self.po_line_id:
                errors["receipt_line"] = "That receipt line was booked against a different order line."

        if self.receipt_line_id and tenant_id:
            if self.receipt_line.goods_receipt.tenant_id != tenant_id:
                errors["receipt_line"] = "That goods receipt belongs to another workspace."

        for name in ("item", "gl_account", "tax_code"):
            chosen = getattr(self, name, None)
            if chosen is not None and tenant_id and chosen.tenant_id != tenant_id:
                errors[name] = "That record belongs to another workspace."

        quantity = _finite(self.quantity)
        if quantity is None or quantity.copy_abs() >= _QUANTITY_CEILING:
            errors["quantity"] = "Enter a quantity below 10,000,000,000."
        unit_price = _finite(self.unit_price)
        if unit_price is None or unit_price.copy_abs() >= _UNIT_PRICE_CEILING:
            errors["unit_price"] = "Enter a unit price below 1,000,000,000,000."

        if invoice is not None and quantity is not None and unit_price is not None:
            # Sign consistency with the header: a credit memo settles a claim, so every line on
            # one must REDUCE what is owed. Checked here as well as on the header so the error
            # lands on the line the user is editing.
            value = quantity * unit_price
            if invoice.invoice_type == "credit_memo" and value > ZERO:
                errors["unit_price"] = "A credit memo line cannot carry a positive value."
            elif invoice.invoice_type != "credit_memo" and value < ZERO:
                errors["unit_price"] = "Only a credit memo may carry a negative line."
            # A non-PO invoice has no ordered line to derive the expense account from, so the
            # account has to be named — it is the only way the bill can post.
            if invoice.match_basis == "none" and self.gl_account_id is None:
                errors["gl_account"] = "A line on a non-PO invoice must name the GL account to post to."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        #: SIGNED — a credit memo's line total is negative by design, so never abs() this.
        self.line_total = q2(_as_decimal(self.quantity) * _as_decimal(self.unit_price))

        #: Mirroring is skipped when ``update_fields`` is passed: that shape is a partial write of
        #: one derived column (``run_match()`` writing ``matched_qty``), which must not also
        #: re-point or refill the descriptive fields.
        if kwargs.get("update_fields") is None and self.po_line_id:
            source = self.po_line
            if not (self.description or "").strip():
                self.description = (source.item_description or "")[:255]
            if not (self.sku_hint or "").strip():
                self.sku_hint = (source.sku_hint or "")[:64]
            if not (self.uom_hint or "").strip():
                self.uom_hint = (source.uom_hint or "")[:32]

        super().save(*args, **kwargs)

        if kwargs.get("update_fields") is None:
            # The header money follows the lines. Only on a FULL write: recalc_totals() itself
            # saves the header with update_fields, and re-entering from there would loop.
            self.invoice.recalc_totals()
