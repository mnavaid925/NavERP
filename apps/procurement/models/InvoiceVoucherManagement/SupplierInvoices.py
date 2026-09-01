"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoice [SIV-].

**Invoice Capture / OCR**, **3-Way Match**, **Invoice Approval Workflow**, **Payment Scheduling**,
**Invoice Dispute Management**, **Early Payment Discount Capture**, **Duplicate Invoice Detection**
and **Invoice Dashboard** are the eight NavERP.md bullets that make up this sub-module. This
module owns the invoice HEADER — the supplier's claim against us — and the matching engine that
judges it against what we ordered and what we received.

**Ownership (L29/L36).** The document spine stays where it already lives: what we ordered is
``scm.PurchaseOrder`` / ``scm.PurchaseOrderLine``, what arrived is ``scm.GoodsReceiptNote`` /
``scm.GoodsReceiptLine``, and the money is ``accounting.Bill`` + ``accounting.JournalEntry``. This
model POINTS at all of them and never re-declares one. It is also the ONLY place in 6.13 that
writes the ledger, and it does so in exactly one transition (``approve``) — a parked, blocked or
disputed invoice never reaches the GL.

**The one writer rule for the ledger.** ``approve()`` creates one ``Bill`` and one ``JournalEntry``
inside a single ``transaction.atomic()`` that opens with ``if self.journal_entry_id: return False``.
That guard is the double-click / back-button guard (C1): without it a second submit would mint a
second bill for the same invoice. Every other transition moves only ``status``.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from apps.accounting.models import Bill, BillLine, GLAccount, JournalEntry, JournalLine
from apps.procurement.models._base import *  # noqa: F401,F403
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` (the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import).
from apps.procurement.models.InvoiceVoucherManagement.MatchVariances import InvoiceMatchVariance
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine

#: Quantization used for every derived variance figure — four decimal places is enough that a
#: percentage of a sub-cent variance still survives rounding.
_VARIANCE_DP = Decimal("0.0001")

#: Account codes the GL resolution tries first, per leg. The fallback is the account TYPE, so a
#: workspace whose chart of accounts uses different numbering still posts (see ``_gl_account``).
EXPENSE_GL_CODES = ("5000", "5100", "5200", "6000", "6100")
AP_CONTROL_GL_CODES = ("2000", "2010", "2100")
TAX_GL_CODES = ("1400", "1410", "2300", "2310")
DISCOUNT_GL_CODES = ("5900", "5950", "7000")


def _as_decimal(value):
    """``value`` as a finite ``Decimal`` — ``ZERO`` for anything unusable (L35/L11).

    ``Decimal("nan")`` and ``Decimal("Infinity")`` both PARSE cleanly and then raise on the
    COMPARISON, and a hand-fed string can produce either, so every figure that arrives from
    outside this module goes through here before it is compared.
    """
    try:
        number = Decimal(value if value is not None else ZERO)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return ZERO
    return number if number.is_finite() else ZERO


def resolve_tolerance(expected, actual, *, pct_upper=None, pct_lower=None,
                      abs_upper=None, abs_lower=None, cap=None):
    """Return ``(outcome, variance_abs, variance_pct, tol_pct_applied, tol_abs_applied)``.

    **More restrictive wins:** a percentage band and an absolute band are checked independently and
    EITHER firing is a breach, so declaring both can only ever narrow what is accepted. A ``None``
    band is "no band" and never breaches — that is what lets most of this model's absolute bands
    ship as ``None`` pending configuration.

    ``variance_abs`` is SIGNED (``actual - expected``), so a caller can tell an over-charge from an
    under-charge; ``outcome`` is ``"block"`` when breached, ``"warn"`` when merely non-zero, and
    ``"auto_accept"`` when the two figures agree exactly. ``cap="warn"`` downgrades a ``block`` and
    is reserved for the two checks that must never hold an invoice on their own (tax rounding and a
    duplicate suspicion, §8.1/§8.2).
    """
    expected_value = _as_decimal(expected)
    actual_value = _as_decimal(actual)

    variance_abs = (actual_value - expected_value).quantize(_VARIANCE_DP)
    variance_pct = None
    if expected_value != ZERO:
        variance_pct = (variance_abs / expected_value * Decimal("100")).quantize(_VARIANCE_DP)

    tol_pct_applied = None
    tol_abs_applied = None
    breached = False

    if pct_upper is not None and variance_pct is not None and variance_pct > pct_upper:
        breached = True
        tol_pct_applied = pct_upper
    if abs_upper is not None and variance_abs > abs_upper:
        breached = True
        tol_abs_applied = abs_upper
    if pct_lower is not None and variance_pct is not None and variance_pct < -pct_lower:
        breached = True
        tol_pct_applied = pct_lower
    if abs_lower is not None and variance_abs < -abs_lower:
        breached = True
        tol_abs_applied = abs_lower

    if breached:
        outcome = "block"
    elif variance_abs != ZERO:
        outcome = "warn"
    else:
        outcome = "auto_accept"

    if cap == "warn" and outcome == "block":
        outcome = "warn"
    return outcome, variance_abs, variance_pct, tol_pct_applied, tol_abs_applied


def _gl_account(tenant, codes, account_type):
    """Resolve one ledger leg's ``GLAccount`` — by code first, then by account type.

    ``JournalLine.gl_account`` is ``PROTECT`` and NOT nullable, and ``GLAccount`` carries no
    AP/cash subtype, so there is no "the AP account" to look up by flag. Trying the conventional
    codes first keeps a standard chart of accounts exact; falling back to the first active account
    of the right TYPE keeps a workspace with its own numbering postable rather than dead.
    """
    return (GLAccount.objects.filter(tenant=tenant, is_active=True, code__in=codes).first()
            or GLAccount.objects.filter(tenant=tenant, is_active=True,
                                        account_type=account_type).order_by("code").first())


class SupplierInvoice(TenantNumbered):
    """One supplier invoice (or credit/debit memo) [SIV-].

    Lifecycle::

        draft -> parked -> captured -> blocked -> pending_approval -> approved -> scheduled -> paid
                    ^          |          ^              |               |           ^         |
                    +----------+          +--------------+               +-----------+         v
                                     disputed -------+          void <--------------------> reversed

    ``status`` moves ONLY through the verb methods at the bottom of this class, each of which
    re-checks its own guard INSIDE itself and returns a bool — hiding a button in a template does
    not stop a direct POST, and a double-submitted approval must not mint a second bill.

    **The match engine.** ``run_match()`` is the ordered sequence that judges the claim against the
    order and the receipt. It is deliberately RE-RUNNABLE: it deletes and rebuilds
    ``InvoiceMatchVariance`` rows every time, so re-matching after a correction can never leave a
    stale verdict behind.
    """

    NUMBER_PREFIX = "SIV"

    STATUS_CHOICES = [("draft", "Draft"), ("parked", "Parked"), ("captured", "Captured"), ("blocked", "Blocked"),
                      ("disputed", "Disputed"), ("pending_approval", "Pending Approval"), ("approved", "Approved"),
                      ("scheduled", "Scheduled"), ("paid", "Paid"), ("void", "Void"), ("reversed", "Reversed")]
    INVOICE_TYPE_CHOICES = [("standard", "Standard Invoice"), ("credit_memo", "Credit Memo"),
                            ("debit_memo", "Debit Memo"), ("prepayment", "Prepayment / Down-payment Request"),
                            ("service", "Service Invoice (PO-less)")]
    MATCH_BASIS_CHOICES = [("quantity", "Quantity"), ("amount", "Amount"), ("none", "No Match")]
    MATCH_STATUS_CHOICES = [("not_run", "Not Run"), ("matched", "Matched"),
                            ("within_tolerance", "Matched Within Tolerance"), ("price_variance", "Price Variance"),
                            ("quantity_variance", "Quantity Variance"), ("total_variance", "Total Amount Variance"),
                            ("fx_variance", "FX / Conversion-Rate Variance"), ("no_receipt", "No Receipt Posted"),
                            ("over_invoiced", "Over-Invoiced"), ("duplicate_suspect", "Duplicate Suspect")]
    SOURCE_CHOICES = [("manual", "Manual Keying"), ("pdf_text_layer", "PDF Text-Layer Extraction"),
                      ("e_invoice_xml", "Structured E-Invoice (XML)"), ("vis", "Vendor Portal Submission"), ("ocr", "OCR Engine")]
    DISCOUNT_BASE_CHOICES = [("net_of_tax", "Net of Tax"), ("gross", "Gross (Incl. Tax)")]

    # -- tolerance policy -------------------------------------------------------------------
    #: These are the workspace's bands, not per-record settings (6.12 keeps per-vendor/sku
    #: overrides in its own policy table; 6.13 ships the flat set research §8 settled on).
    PRICE_TOL_PCT_UPPER = Decimal("2.00")
    PRICE_TOL_PCT_LOWER = None            # no floor — under-billing is not a risk
    PRICE_TOL_ABS_UPPER = None            # absolute band ships None (orchestrator decision)
    QTY_TOL_PCT_UPPER = Decimal("0.00")   # invoiced vs RECEIVED — never pay for more than arrived
    QTY_TOL_ABS_UPPER = None
    QTY_TOL_PCT_UPPER_NO_GRN = Decimal("5.00")
    QTY_TOL_PCT_LOWER = Decimal("5.00")
    TOTAL_TOL_PCT = Decimal("1.00")
    TOTAL_TOL_ABS = None
    FX_TOL_PCT = Decimal("1.00")
    #: The ONE absolute band retained: it has no percentage counterpart, and shipping it as None
    #: would make every tax rounding cent a block — directly contradicting research §8.2 ("never
    #: block an invoice on tax rounding alone").
    TAX_TOL_ABS = Decimal("1.00")

    DUPLICATE_WINDOW_DAYS = 90
    DUPLICATE_AMOUNT_TOL_PCT = Decimal("1.00")
    DISCOUNT_GRACE_DAYS = 0
    DISCOUNT_ANNUALISATION_DAYS = 360

    #: Past these an invoice is a closed book — no edit, no match, no re-approval.
    TERMINAL_STATUSES = ("paid", "void", "reversed")
    #: The window in which the header and its lines may still be corrected.
    EDITABLE_STATUSES = ("draft", "parked", "captured")

    ALLOWED_TRANSITIONS = {
        "draft": ("parked", "captured", "void"),
        "parked": ("draft", "captured", "void"),
        "captured": ("blocked", "pending_approval", "void"),
        "blocked": ("pending_approval", "disputed", "void"),
        "disputed": ("blocked", "pending_approval", "void"),
        "pending_approval": ("approved", "blocked", "void"),
        "approved": ("scheduled", "void", "reversed"),
        "scheduled": ("paid", "approved", "void"),
        "paid": ("reversed",),
        "void": (),
        "reversed": (),
    }

    #: Which ``InvoiceMatchVariance.variance_type`` maps to which header ``match_status``. The
    #: FIRST breaching check wins, so a price breach reads as a price variance even when the total
    #: is out of band too.
    MATCH_STATUS_BY_TYPE = {
        "price": "price_variance",
        "quantity": "quantity_variance",
        "quantity_no_receipt": "quantity_variance",
        "over_invoice": "over_invoiced",
        "total_amount": "total_variance",
        "fx_rate": "fx_variance",
        "missing_receipt": "no_receipt",
        "missing_po": "not_run",
        "duplicate": "duplicate_suspect",
        "tax": "within_tolerance",
    }

    # -- badge maps (L33) ---------------------------------------------------------------------
    # theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    # badge-slate. A semantic ``badge-success`` / ``badge-danger`` renders COMPLETELY UNSTYLED.
    STATUS_CSS = {
        "draft": "badge-muted",
        "parked": "badge-slate",
        "captured": "badge-info",
        "blocked": "badge-red",
        "disputed": "badge-amber",
        "pending_approval": "badge-amber",
        "approved": "badge-green",
        "scheduled": "badge-info",
        "paid": "badge-green",
        "void": "badge-slate",
        "reversed": "badge-slate",
    }
    MATCH_STATUS_CSS = {
        "not_run": "badge-muted",
        "matched": "badge-green",
        "within_tolerance": "badge-info",
        "price_variance": "badge-amber",
        "quantity_variance": "badge-amber",
        "total_variance": "badge-amber",
        "fx_variance": "badge-amber",
        "no_receipt": "badge-amber",
        "over_invoiced": "badge-red",
        "duplicate_suspect": "badge-red",
    }
    SOURCE_CSS = {
        "manual": "badge-muted",
        "pdf_text_layer": "badge-info",
        "e_invoice_xml": "badge-info",
        "vis": "badge-slate",
        "ocr": "badge-slate",
    }

    # -- document spine (L36: every one of these is OWNED elsewhere) --------------------------
    vendor = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                               related_name="procurement_supplier_invoices")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="procurement_supplier_invoices")
    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="procurement_supplier_invoices")
    bill = models.ForeignKey("accounting.Bill", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
                             related_name="procurement_supplier_invoices")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      editable=False, related_name="procurement_supplier_invoices")
    payment_term = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="procurement_supplier_invoices")
    # accounting.Currency is GLOBAL (no tenant column) — never tenant-scoped, never passed to
    # _reject_foreign.
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_supplier_invoices")
    tax_code = models.ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_supplier_invoices")
    source_submission = models.ForeignKey("procurement.VendorInvoiceSubmission", on_delete=models.SET_NULL,
                                          null=True, blank=True, editable=False,
                                          related_name="procurement_supplier_invoices")
    document = models.ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_supplier_invoices")
    # A duplicate is a SUSPICION, never an auto-rejection (§8.1): linking it preserves the evidence
    # and leaves the decision to a person.
    duplicate_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
                                     related_name="duplicates")

    # -- identity -----------------------------------------------------------------------------
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES, default="standard")
    invoice_number = models.CharField(max_length=64, help_text="The supplier's own invoice number")
    #: Upper-cased alphanumerics only — the key duplicate detection compares, so "INV 100/A" and
    #: "inv-100a" collide the way a human reading both would say they do.
    invoice_number_norm = models.CharField(max_length=64, editable=False, db_index=True)
    external_ref = models.CharField(max_length=64, blank=True)

    # -- dates --------------------------------------------------------------------------------
    invoice_date = models.DateField()
    posting_date = models.DateField(null=True, blank=True)
    #: All three below are DERIVED in ``save()`` from the payment term — a typed due date is how an
    #: AP clerk "forgets" to take a discount.
    due_date = models.DateField(null=True, blank=True, editable=False)
    discount_date = models.DateField(null=True, blank=True, editable=False)
    discount_expiry_date = models.DateField(null=True, blank=True, editable=False)

    # -- early-payment discount ----------------------------------------------------------------
    discount_base = models.CharField(max_length=10, choices=DISCOUNT_BASE_CHOICES, default="net_of_tax")
    #: Days of grace after the contractual discount date — a concession, so it is capped in clean().
    discount_grace_days = models.PositiveSmallIntegerField(default=0)

    # -- money (all derived, editable=False) ---------------------------------------------------
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO, editable=False)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO, editable=False)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO, editable=False)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO, editable=False)
    fx_rate = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True,
                                  validators=[MinValueValidator(ZERO)])

    # -- match result --------------------------------------------------------------------------
    #: Written ONLY by ``run_match()`` — excluded from the form on purpose.
    match_basis = models.CharField(max_length=10, choices=MATCH_BASIS_CHOICES, default="none")
    match_status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES, default="not_run", editable=False)
    match_notes = models.TextField(blank=True, editable=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # -- capture provenance ---------------------------------------------------------------------
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")
    extraction_confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))])
    extraction_raw_text = models.TextField(blank=True)

    notes = models.TextField(blank=True)

    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    editable=False, related_name="procurement_supplier_invoices_approved")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_siv_tnt_status_idx"),
            models.Index(fields=["tenant", "match_status"], name="prc_siv_tnt_match_idx"),
            models.Index(fields=["tenant", "vendor", "invoice_number_norm"], name="prc_siv_tnt_dup_idx"),
            models.Index(fields=["tenant", "discount_date"], name="prc_siv_tnt_disc_idx"),
            models.Index(fields=["tenant", "due_date"], name="prc_siv_tnt_due_idx"),
            # Meta.ordering itself: the register, the dashboard's recent/blocked panels and the
            # duplicate scan all ORDER BY -invoice_date under a tenant predicate, which was a
            # filesort on the module's largest table without this.
            models.Index(fields=["tenant", "-invoice_date"], name="prc_siv_tnt_invdate_idx"),
        ]
        verbose_name = "supplier invoice"

    def __str__(self):
        return f"{self.number or 'SIV'} · {self.invoice_number}"

    # -- identity helpers ---------------------------------------------------------------------

    @staticmethod
    def normalise_invoice_number(value):
        """The duplicate-detection key: upper-case, alphanumerics only, capped at 64."""
        return "".join(c for c in (value or "").upper() if c.isalnum())[:64]

    # -- validation -----------------------------------------------------------------------------

    def clean(self):
        errors = {}
        tenant_id = self.tenant_id

        for name in ("vendor", "purchase_order", "goods_receipt", "bill", "journal_entry",
                     "payment_term", "tax_code", "document", "source_submission", "duplicate_of"):
            chosen = getattr(self, name, None)
            # ``currency`` is deliberately absent — accounting.Currency is GLOBAL, so there is no
            # tenant to compare and checking it would reject every valid choice.
            if chosen is not None and tenant_id and getattr(chosen, "tenant_id", None) != tenant_id:
                errors[name] = "That record belongs to another workspace."

        # L40 §3 — vendor agreement. An invoice against one supplier's order must be FROM that
        # supplier; anything else is either a mis-key or an attempt to draw funds to a third party.
        if self.purchase_order_id and self.vendor_id:
            if self.purchase_order.vendor_id != self.vendor_id:
                errors["purchase_order"] = "That purchase order belongs to a different vendor."
        if self.goods_receipt_id and self.vendor_id:
            order = self.goods_receipt.purchase_order
            grn_vendor_id = order.vendor_id if order is not None else None
            if grn_vendor_id != self.vendor_id:
                errors["goods_receipt"] = "That goods receipt belongs to a different vendor."

        if self.invoice_date and self.posting_date and self.posting_date < self.invoice_date:
            errors["posting_date"] = "The posting date cannot be earlier than the invoice date."

        if self.fx_rate is not None:
            rate = _as_decimal(self.fx_rate)
            if not rate.is_finite() or rate <= ZERO:
                errors["fx_rate"] = "Enter a conversion rate greater than zero."

        if self.discount_grace_days is not None:
            grace = _as_decimal(self.discount_grace_days).to_integral_value()
            if grace < ZERO or grace > Decimal("365"):
                errors["discount_grace_days"] = "Grace days must be between 0 and 365."

        if self.duplicate_of_id and self.pk and self.duplicate_of_id == self.pk:
            errors["duplicate_of"] = "An invoice cannot be a duplicate of itself."

        if not (self.invoice_number or "").strip():
            errors["invoice_number"] = "Enter the supplier's invoice number."

        # Sign consistency: a credit memo's lines must not carry positive value. Checked on EDIT
        # only — on create the lines do not exist yet, and lane B's own clean() catches each line
        # as it is saved.
        if self.pk:
            for line in self.lines.all():
                value = _as_decimal(line.quantity) * _as_decimal(line.unit_price)
                if self.invoice_type == "credit_memo" and value > ZERO:
                    errors["invoice_type"] = (
                        "A credit memo cannot carry a line with a positive value — "
                        f"line {line.pk} is {value}.")
                    break
                if self.invoice_type != "credit_memo" and value < ZERO:
                    errors["invoice_type"] = (
                        "Only a credit memo may carry a negative line — "
                        f"line {line.pk} is {value}.")
                    break

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.invoice_number_norm = self.normalise_invoice_number(self.invoice_number)

        if self.invoice_date and self.payment_term_id:
            term = self.payment_term
            self.due_date = self.invoice_date + timedelta(days=int(term.days_due or 0))
            if term.discount_days:
                self.discount_date = self.invoice_date + timedelta(days=int(term.discount_days))
                self.discount_expiry_date = self.discount_date + timedelta(
                    days=int(self.discount_grace_days or 0))
            else:
                # A term with no discount has no discount window — clearing these is what stops a
                # stale date from an earlier term claiming a discount that no longer exists.
                self.discount_date = None
                self.discount_expiry_date = None
        else:
            self.due_date = None
            self.discount_date = None
            self.discount_expiry_date = None

        super().save(*args, **kwargs)

    # -- derived money --------------------------------------------------------------------------

    def recalc_totals(self, save=True):
        """Re-derive the header money from the lines.

        ``update_fields`` is what makes this safe to call from ``SupplierInvoiceLine.save()``: it
        writes only the four money columns, so it cannot re-enter that line's save and loop.
        """
        rows = list(self.lines.all())
        self.subtotal = q2(sum((_as_decimal(row.line_total) for row in rows), ZERO))
        self.tax_total = q2(sum(
            (q2(_as_decimal(row.line_total) * _as_decimal(row.tax_rate_pct) / Decimal("100"))
             for row in rows), ZERO))
        self.total = q2(_as_decimal(self.subtotal) + _as_decimal(self.tax_total))
        self.amount_paid = self.bill.amount_paid() if self.bill_id else ZERO
        if save:
            self.save(update_fields=["subtotal", "tax_total", "total", "amount_paid", "updated_at"])

    @property
    def is_locked(self):
        return self.status in self.TERMINAL_STATUSES

    @classmethod
    def cumulative_invoiced_qty(cls, po_line):
        """Everything invoiced against one ordered line across every LIVE invoice.

        Derived, never stored: a counter drifts the first time a GRN is cancelled or an invoice is
        reversed, and the correct answer is one aggregate away. Credit memos are excluded — they
        reduce what is owed, they do not un-invoice a delivery.
        """
        if po_line is None:
            return ZERO
        return (SupplierInvoiceLine.objects.filter(po_line=po_line)
                .exclude(invoice__status__in=cls.TERMINAL_STATUSES)
                .exclude(invoice__invoice_type="credit_memo")
                .aggregate(s=Sum("quantity"))["s"] or ZERO)

    @classmethod
    def cumulative_received_qty(cls, po_line):
        """Everything accepted against one ordered line across every LIVE receipt."""
        if po_line is None:
            return ZERO
        return (po_line.receipt_lines.exclude(goods_receipt__status="cancelled")
                .aggregate(s=Sum("quantity_received"))["s"] or ZERO)

    # -- early-payment discount ------------------------------------------------------------------

    def discount_amount(self):
        """What the supplier is offering for paying early, on the agreed base."""
        term = self.payment_term
        if term is None:
            return ZERO
        base = self.subtotal if self.discount_base == "net_of_tax" else self.total
        pct = _as_decimal(term.discount_pct)
        if pct <= ZERO:
            return ZERO
        return q2(abs(_as_decimal(base)) * pct / Decimal("100"))

    def annualised_pct(self):
        """The discount as an annual rate — what "2/10 Net 30" is really worth (36.73%).

        Zero when there is no term, no discount, or a term where the discount window is not
        actually shorter than the due date (a "2/10 Net 10" is a straight price cut, not credit).
        """
        term = self.payment_term
        if term is None:
            return ZERO
        pct = _as_decimal(term.discount_pct)
        days_due = int(term.days_due or 0)
        discount_days = int(term.discount_days or 0)
        if pct <= ZERO or days_due <= discount_days:
            return ZERO
        return q2(pct / (Decimal("100") - pct)
                  * (Decimal(self.DISCOUNT_ANNUALISATION_DAYS) / Decimal(days_due - discount_days))
                  * Decimal("100"))

    # -- duplicate detection ----------------------------------------------------------------------

    def duplicate_candidates(self, limit=10, candidates=None):
        """``[(invoice, [reason, ...]), ...]`` — suspected duplicates of this invoice.

        **Never auto-rejects** (§8.1): a duplicate is a suspicion to be reviewed, and the register
        that ships a silent block is the register AP stops trusting. The normalised invoice number
        is MANDATORY (it is the queryset's own predicate) and a candidate is only reported once it
        scores at least three independent reasons, so a coincidental number match alone is silent.

        ``candidates`` is the batch escape hatch: a caller that is scanning MANY invoices at once
        (the duplicate board) fetches every peer sharing a normalised number in ONE query and
        hands this row's bucket in, so the scoring below runs without a database hit. The bucket
        must already be this workspace's rows with this row's ``invoice_number_norm``, in the same
        ``-invoice_date, -id`` order — the predicate this method would have applied itself.
        """
        if self.tenant_id is None or not self.invoice_number_norm:
            return []
        if candidates is None:
            rows = (type(self).objects
                    .filter(tenant=self.tenant_id, invoice_number_norm=self.invoice_number_norm)
                    .select_related("vendor", "currency", "payment_term")
                    .order_by("-invoice_date", "-id"))
            if self.pk:
                rows = rows.exclude(pk=self.pk)
            rows = rows[:limit]
        else:
            rows = [other for other in candidates if other.pk != self.pk][:limit]

        window = timedelta(days=self.DUPLICATE_WINDOW_DAYS)
        out = []
        for other in rows:
            reasons = ["normalised invoice number matches"]
            if self.vendor_id and other.vendor_id == self.vendor_id:
                reasons.append("same vendor")
            outcome, _abs, _pct, _tp, _ta = resolve_tolerance(
                self.total, other.total,
                pct_upper=self.DUPLICATE_AMOUNT_TOL_PCT, pct_lower=self.DUPLICATE_AMOUNT_TOL_PCT)
            if outcome != "block":
                reasons.append("amount within 1%")
            if self.invoice_date and other.invoice_date:
                if abs(other.invoice_date - self.invoice_date) <= window:
                    reasons.append(f"invoice date within {self.DUPLICATE_WINDOW_DAYS} days")
            if len(reasons) >= 3:
                out.append((other, reasons))
        return out

    # -- the match engine ----------------------------------------------------------------------

    def run_match(self, user=None):
        """Judge this invoice against the order and the receipt. Returns ``(status, counts)``.

        The check sequence is ORDERED and the FIRST breach wins: a price breach is reported as a
        price variance even when the total is out of band too, because fixing the unit price is
        what the supplier has to do. Re-runnable — the previous run's variances are deleted first.

        ``user`` is accepted for symmetry with the other verbs; authorship of the run is recorded
        by the caller's audit row.

        Callers fetch the row with ``select_for_update()`` (the 6.12 discipline — the view holds
        the lock, the method re-checks its own guard), so the instance they hold afterwards still
        carries the verdict they just asked for.
        """
        counts = {"auto_accept": 0, "warn": 0, "block": 0}

        if self.is_locked:
            return self.status, counts

        if self.invoice_type == "credit_memo":
            # A credit memo settles a claim; there is nothing to three-way match it against. The
            # status is deliberately NOT touched — a memo captured but not yet approved stays
            # captured.
            self.variances.all().delete()
            self.match_status = "not_run"
            self.match_notes = "Credit memos are not three-way matched."
            self.save(update_fields=["match_status", "match_notes", "updated_at"])
            return self.status, counts

        with transaction.atomic():
            lines = list(self.lines.select_related("po_line", "receipt_line", "gl_account").order_by("id"))

            recorded = []

            def record(*, variance_type, basis, expected=ZERO, actual=ZERO, invoice_line=None,
                       pct_upper=None, pct_lower=None, abs_upper=None, abs_lower=None,
                       message="", outcome_override=None, cap=None):
                variance = InvoiceMatchVariance.record(
                    invoice=self, invoice_line=invoice_line, variance_type=variance_type,
                    basis=basis, expected=expected, actual=actual, pct_upper=pct_upper,
                    pct_lower=pct_lower, abs_upper=abs_upper, abs_lower=abs_lower,
                    message=message, outcome_override=outcome_override, cap=cap)
                counts[variance.outcome] = counts.get(variance.outcome, 0) + 1
                recorded.append(variance)
                return variance

            # 1 — previous verdicts are stale the moment anything is corrected.
            self.variances.all().delete()

            # 2 — the basis: three-way (quantity), two-way (amount), or non-PO (none).
            if self.purchase_order_id is None:
                basis = "none"
            elif self.goods_receipt_id or any(line.receipt_line_id for line in lines):
                basis = "quantity"
            else:
                basis = "amount"
            self.match_basis = basis

            # 3 — header vendor agreement. A mismatch here invalidates the whole document, not a
            # line, so both are unconditional blocks.
            if self.purchase_order_id and self.vendor_id and self.purchase_order.vendor_id != self.vendor_id:
                record(variance_type="missing_po", basis="header", outcome_override="block",
                       message="The purchase order belongs to a different vendor.")
            if self.goods_receipt_id and self.vendor_id:
                order = self.goods_receipt.purchase_order
                if (order.vendor_id if order is not None else None) != self.vendor_id:
                    record(variance_type="missing_receipt", basis="header", outcome_override="block",
                           message="The goods receipt belongs to a different vendor.")

            # 4 — per line, first breach wins and moves to the next line.
            for line in lines:
                po_line = line.po_line if line.po_line_id else None
                receipt_line = line.receipt_line if line.receipt_line_id else None

                if basis == "none":
                    # A non-PO line has nowhere to post to unless someone names the account.
                    if line.gl_account_id is None:
                        record(invoice_line=line, variance_type="missing_po", basis="header",
                               outcome_override="block",
                               message="Non-PO line requires a GL account.")
                    continue

                if po_line is None:
                    record(invoice_line=line, variance_type="missing_po", basis="po",
                           expected=ZERO, actual=_as_decimal(line.quantity), outcome_override="block",
                           message="This line has no purchase-order line to match against.")
                    continue

                if basis == "quantity":
                    if receipt_line is None:
                        # No receipt yet — the only honest comparison left is against the ORDER,
                        # on the wider no-GRN band, because the goods may simply not have arrived.
                        outcome, _a, _p, _tp, _ta = resolve_tolerance(
                            _as_decimal(po_line.quantity), _as_decimal(line.quantity),
                            pct_upper=self.QTY_TOL_PCT_UPPER_NO_GRN)
                        record(invoice_line=line, variance_type="quantity_no_receipt", basis="po",
                               expected=_as_decimal(po_line.quantity),
                               actual=_as_decimal(line.quantity),
                               pct_upper=self.QTY_TOL_PCT_UPPER_NO_GRN,
                               message="No goods receipt has been posted for this line.")
                        if outcome == "block":
                            continue
                    else:
                        received = _as_decimal(receipt_line.quantity_received)
                        outcome_line, _a, _p, _tp, _ta = resolve_tolerance(
                            received, _as_decimal(line.quantity),
                            pct_upper=self.QTY_TOL_PCT_UPPER, abs_upper=self.QTY_TOL_ABS_UPPER)
                        record(invoice_line=line, variance_type="quantity", basis="receipt",
                               expected=received, actual=_as_decimal(line.quantity),
                               pct_upper=self.QTY_TOL_PCT_UPPER, abs_upper=self.QTY_TOL_ABS_UPPER,
                               message="Invoiced quantity differs from the quantity received.")
                        # Cumulative: two invoices of 60 against a receipt of 100 is an
                        # over-invoice even though neither row breaches on its own.
                        cum_received = _as_decimal(type(self).cumulative_received_qty(po_line))
                        cum_invoiced = _as_decimal(type(self).cumulative_invoiced_qty(po_line))
                        outcome_cum, _a, _p, _tp, _ta = resolve_tolerance(
                            cum_received, cum_invoiced,
                            pct_upper=self.QTY_TOL_PCT_UPPER, abs_upper=self.QTY_TOL_ABS_UPPER)
                        record(invoice_line=line, variance_type="quantity", basis="receipt",
                               expected=cum_received, actual=cum_invoiced,
                               pct_upper=self.QTY_TOL_PCT_UPPER, abs_upper=self.QTY_TOL_ABS_UPPER,
                               message="Cumulative invoiced quantity differs from the quantity received.")
                        if outcome_line == "block" or outcome_cum == "block":
                            continue

                # Over-invoicing: the cumulative position against the ORDER, not the receipt —
                # this is the check that stops a supplier billing the same 100 units twice.
                ordered = _as_decimal(po_line.quantity)
                allowance = ordered * _as_decimal(self.QTY_TOL_PCT_UPPER) / Decimal("100")
                cum_invoiced = _as_decimal(type(self).cumulative_invoiced_qty(po_line))
                if cum_invoiced > ordered + allowance:
                    record(invoice_line=line, variance_type="over_invoice", basis="po",
                           expected=ordered, actual=cum_invoiced, outcome_override="block",
                           message="Cumulative invoiced quantity exceeds the ordered quantity.")
                    continue

                record(invoice_line=line, variance_type="price", basis="po",
                       expected=_as_decimal(po_line.unit_price), actual=_as_decimal(line.unit_price),
                       pct_upper=self.PRICE_TOL_PCT_UPPER, pct_lower=self.PRICE_TOL_PCT_LOWER,
                       abs_upper=self.PRICE_TOL_ABS_UPPER,
                       message="Unit price differs from the purchase order.")

            # 5 — header-level checks.
            expected_total = ZERO
            expected_tax = ZERO
            for line in lines:
                line_po = line.po_line if line.po_line_id else None
                line_value = _as_decimal(line.line_total)
                if line_po is not None:
                    expected_total += _as_decimal(line_po.unit_price) * _as_decimal(line.quantity)
                else:
                    expected_total += line_value
                expected_tax += q2(line_value * _as_decimal(line.tax_rate_pct) / Decimal("100"))

            if basis != "none":
                record(variance_type="total_amount", basis="header",
                       expected=q2(expected_total), actual=_as_decimal(self.total),
                       pct_upper=self.TOTAL_TOL_PCT, pct_lower=self.TOTAL_TOL_PCT,
                       abs_upper=self.TOTAL_TOL_ABS, abs_lower=self.TOTAL_TOL_ABS,
                       message="Header total differs from the value of the matched lines.")

            if (self.fx_rate is not None and self.purchase_order_id
                    and self.currency_id != self.purchase_order.currency_id):
                # Only meaningful when the two documents are in different currencies: the billed
                # value CONVERTED at the declared rate is compared with the ordered value.
                record(variance_type="fx_rate", basis="header",
                       expected=q2(expected_total),
                       actual=q2(expected_total * _as_decimal(self.fx_rate)),
                       pct_upper=self.FX_TOL_PCT, pct_lower=self.FX_TOL_PCT,
                       message="Converted value differs from the order value at this conversion rate.")

            record(variance_type="tax", basis="header",
                   expected=q2(expected_tax), actual=_as_decimal(self.tax_total),
                   abs_upper=self.TAX_TOL_ABS, abs_lower=self.TAX_TOL_ABS,
                   cap="warn", message="Tax differs from the line-derived tax amount.")

            for candidate, reasons in self.duplicate_candidates():
                record(variance_type="duplicate", basis="header",
                       expected=_as_decimal(self.total), actual=_as_decimal(candidate.total),
                       pct_upper=self.DUPLICATE_AMOUNT_TOL_PCT,
                       pct_lower=self.DUPLICATE_AMOUNT_TOL_PCT,
                       cap="warn", message=f"Possible duplicate of {candidate.number} ("
                                           f"{'; '.join(reasons)}).")

            # 6/7 — fold the verdict into the header.
            block_types = [v.variance_type for v in recorded if v.outcome == "block"]
            has_duplicate = any(v.variance_type == "duplicate" for v in recorded)
            has_warn = any(v.outcome == "warn" for v in recorded)

            if block_types:
                self.status = "blocked"
                self.match_status = self.MATCH_STATUS_BY_TYPE.get(block_types[0], "not_run")
            elif has_duplicate:
                # A duplicate never BLOCKS a variance (cap="warn", §8.1) but it does hold the
                # invoice: paying twice is the one error AP cannot recover cheaply.
                self.status = "blocked"
                self.match_status = "duplicate_suspect"
            else:
                self.status = "pending_approval"
                self.match_status = "within_tolerance" if has_warn else "matched"

            # 8 — accepted quantity per line: never more than arrived, never more than ordered,
            # never more than was invoiced.
            for line in lines:
                if line.receipt_line_id:
                    ceiling = _as_decimal(line.receipt_line.quantity_received)
                elif line.po_line_id:
                    ceiling = _as_decimal(line.po_line.quantity)
                else:
                    ceiling = _as_decimal(line.quantity)
                matched = max(ZERO, min(_as_decimal(line.quantity), ceiling))
                if _as_decimal(line.matched_qty) != matched:
                    line.matched_qty = matched
                    line.save(update_fields=["matched_qty"])

            self.save(update_fields=["match_basis", "match_status", "status", "updated_at"])
            return self.status, counts

    # -- the ledger (§8.10) ------------------------------------------------------------------------

    def approve(self, user):
        """Approve a matched invoice — the ONLY transition that touches the ledger.

        Writes one ``accounting.Bill`` (with one ``BillLine`` per invoice line) and one balanced
        ``accounting.JournalEntry``, all inside a single transaction that opens with the
        ``journal_entry_id`` guard. If any required GL account cannot be resolved the whole thing
        raises ``ValidationError`` and rolls back, so there is never a bill without its entry or an
        unbalanced entry without its bill.
        """
        if self.status != "pending_approval":
            return False

        with transaction.atomic():
            # The double-click / back-button guard (C1): a second submit finds the entry already
            # written and no-ops instead of minting a second bill for the same invoice. The row
            # lock is the caller's — every view that can post fetches with select_for_update().
            if self.journal_entry_id:
                return False
            if self.status != "pending_approval":
                return False

            # Re-derive the header money so the journal is built from the same figures the bill is.
            self.recalc_totals(save=True)
            lines = list(self.lines.select_related("gl_account", "tax_code").order_by("id"))

            expense_account = _gl_account(self.tenant_id, EXPENSE_GL_CODES, "expense")
            if expense_account is None:
                raise ValidationError("No expense GL account is configured for this workspace — "
                                      "the invoice was not posted.")
            ap_account = _gl_account(self.tenant_id, AP_CONTROL_GL_CODES, "liability")
            if ap_account is None:
                raise ValidationError("No AP control GL account is configured for this workspace — "
                                      "the invoice was not posted.")
            tax_account = None
            if _as_decimal(self.tax_total) != ZERO:
                tax_account = _gl_account(self.tenant_id, TAX_GL_CODES, "liability")
                if tax_account is None:
                    raise ValidationError("No tax GL account is configured for this workspace — "
                                          "the invoice was not posted.")

            subtotal = q2(self.subtotal)
            tax_total = q2(self.tax_total)
            total = q2(self.total)
            discount = self.discount_amount()

            bill = Bill.objects.create(
                tenant=self.tenant,
                party=self.vendor,
                payment_terms=self.payment_term,
                bill_date=self.invoice_date,
                due_date=self.due_date,
                currency=self.currency,
                status="approved",
                document=self.document,
            )
            for line in lines:
                BillLine.objects.create(
                    bill=bill,
                    description=(line.description or line.sku_hint or "Invoice line")[:255],
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_rate_pct=line.tax_rate_pct,
                    gl_account=line.gl_account or expense_account,
                )
            bill.recalc_totals()

            self.posting_date = self.posting_date or timezone.localdate()
            entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_type="invoice",
                status="posted",
                entry_date=self.posting_date,
                reference=(self.invoice_number or "")[:100],
                description=f"Supplier invoice {self.number}",
                created_by=user,
            )

            legs = [(expense_account, subtotal, ZERO)]
            if tax_account is not None and tax_total != ZERO:
                # Debit the input tax when it is a charge; credit it on a (negative) tax credit.
                legs.append((tax_account, tax_total, ZERO) if tax_total > ZERO
                            else (tax_account, ZERO, -tax_total))
            legs.append((ap_account, ZERO, total))
            if discount > ZERO:
                discount_account = _gl_account(self.tenant_id, DISCOUNT_GL_CODES, "income")
                if discount_account is not None:
                    # Gross method: AP is credited in full and then debited by the discount, which
                    # is recognised as purchase discounts received. Balances with or without it.
                    legs.append((ap_account, discount, ZERO))
                    legs.append((discount_account, ZERO, discount))

            for account, debit, credit in legs:
                if _as_decimal(debit) == ZERO and _as_decimal(credit) == ZERO:
                    continue
                JournalLine.objects.create(
                    entry=entry, gl_account=account, debit=debit, credit=credit,
                    party=self.vendor, currency=self.currency,
                    description=f"{self.invoice_number}"[:255],
                )

            self.bill = bill
            self.journal_entry = entry
            self.approved_by = user if getattr(user, "pk", None) else None
            self.approved_at = timezone.now()
            self.status = "approved"
            self.save(update_fields=["bill", "journal_entry", "approved_by", "approved_at",
                                    "posting_date", "status", "updated_at"])
        return True

    def reverse(self, user):
        """Reverse a posted invoice. Mirrors the entry — it never edits the original.

        The original ``JournalEntry`` is immutable once posted (accounting 2.2 invariant), so the
        correction is a NEW entry with the debits and credits swapped and ``reversal_of`` pointing
        back at it.
        """
        if self.status not in ("paid", "approved") or self.journal_entry_id is None:
            return False

        with transaction.atomic():
            if self.status not in ("paid", "approved") or self.journal_entry_id is None:
                return False

            entry = JournalEntry.objects.create(
                tenant=self.tenant,
                entry_type="reversal",
                status="posted",
                entry_date=self.posting_date or timezone.localdate(),
                reference=(self.invoice_number or "")[:100],
                description=f"Reversal of supplier invoice {self.number}",
                reversal_of=self.journal_entry,
                created_by=user,
            )
            for original in self.journal_entry.lines.select_related("gl_account").order_by("id"):
                JournalLine.objects.create(
                    entry=entry, gl_account=original.gl_account,
                    debit=original.credit, credit=original.debit,
                    party=original.party, currency=original.currency,
                    description=f"Reversal: {self.invoice_number}"[:255],
                )

            self.status = "reversed"
            self.save(update_fields=["status", "updated_at"])
        return True

    # -- lifecycle verbs -------------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool, and each writes only its
    # own columns through update_fields.

    def park(self):
        """Set aside a half-keyed invoice — the supplier's number is missing, the goods have not
        arrived, and the capture queue must be able to move on."""
        if self.status != "draft":
            return False
        self.status = "parked"
        self.save(update_fields=["status", "updated_at"])
        return True

    def unpark(self):
        if self.status != "parked":
            return False
        self.status = "draft"
        self.save(update_fields=["status", "updated_at"])
        return True

    def capture(self):
        """The invoice is complete and legible — it is now ready to be matched."""
        if self.status not in ("draft", "parked"):
            return False
        self.status = "captured"
        self.save(update_fields=["status", "updated_at"])
        return True

    def block(self, reason=""):
        """Hold the invoice. The reason is recorded so the next reader knows who to call."""
        if self.status not in ("captured", "disputed", "pending_approval"):
            return False
        self.status = "blocked"
        if reason:
            self.match_notes = reason[:2000]
        self.save(update_fields=["status", "match_notes", "updated_at"])
        return True

    def raise_dispute(self):
        """Escalate a blocked invoice to the supplier. Requires at least one OPEN variance: a
        dispute with nothing to point at cannot be answered."""
        if self.status != "blocked":
            return False
        if not self.variances.filter(resolution="open").exists():
            return False
        self.status = "disputed"
        self.save(update_fields=["status", "updated_at"])
        return True

    def submit_for_approval(self):
        if self.status not in ("captured", "disputed"):
            return False
        self.status = "pending_approval"
        self.save(update_fields=["status", "updated_at"])
        return True

    def send_back(self, reason=""):
        """Approver refuses it. Back to blocked, carrying why."""
        if self.status != "pending_approval":
            return False
        self.status = "blocked"
        if reason:
            self.match_notes = reason[:2000]
        self.save(update_fields=["status", "match_notes", "updated_at"])
        return True

    def override(self, user):
        """Admin override: accept every blocking variance and move the invoice on.

        This is the deliberate escape hatch for a breach that is real but accepted (a price rise
        agreed by phone). It is admin-gated in the view, it resolves the variances individually so
        the trail shows WHAT was accepted, and it records the actor in ``match_notes``.
        """
        if self.status != "blocked":
            return False
        # Materialised BEFORE the loop: counting the queryset afterwards would re-query and report
        # zero, because every row in it has just been resolved.
        blocking = list(self.variances.filter(resolution="open", outcome="block"))
        for variance in blocking:
            variance.accept(user)
        self.status = "pending_approval"
        actor = getattr(user, "username", None) or "an administrator"
        self.match_notes = (f"Overridden by {actor} — {len(blocking)} blocking variance(s) "
                            f"accepted.")[:2000]
        self.save(update_fields=["status", "match_notes", "updated_at"])
        return True

    def schedule(self):
        if self.status != "approved":
            return False
        self.status = "scheduled"
        self.save(update_fields=["status", "updated_at"])
        return True

    def unschedule(self):
        if self.status != "scheduled":
            return False
        self.status = "approved"
        self.save(update_fields=["status", "updated_at"])
        return True

    def mark_paid(self):
        if self.status != "scheduled":
            return False
        self.status = "paid"
        self.save(update_fields=["status", "updated_at"])
        return True

    def void(self, user, reason=""):
        """Withdraw the invoice. Any non-terminal status; the reason is kept on the record."""
        if self.is_locked:
            return False
        self.status = "void"
        if reason:
            self.notes = f"{reason}\n{self.notes or ''}".strip()
        self.save(update_fields=["status", "notes", "updated_at"])
        return True

    # -- badge helpers (L33) ---------------------------------------------------------------------

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def match_status_css(self):
        return self.MATCH_STATUS_CSS.get(self.match_status, "badge-slate")

    @property
    def source_css(self):
        return self.SOURCE_CSS.get(self.source, "badge-slate")
