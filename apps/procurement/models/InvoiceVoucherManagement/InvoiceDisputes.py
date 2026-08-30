"""Procurement 6.13 Invoice & Voucher Management — InvoiceDispute [DSP-].

**Invoice Dispute Management** is one of the eight NavERP.md bullets in this sub-module. It is
the record of a claim we are NOT paying yet: what part of the supplier's invoice is contested,
why, who owes the answer, and how it was eventually settled.

**Ownership (L29/L36).** The dispute points at the invoice (lane A) and, optionally, at the one
line (lane B) the argument is about; it never re-declares either. ``supplier`` is DENORMALISED
off ``invoice.vendor`` in ``save()`` so the register can be filtered and read without walking a
join on every row — it is not a second source of truth, and it is not a form field.

**Status moves only through the verb methods at the bottom of this class.** Each one re-checks
its own guard INSIDE itself and returns a bool: hiding a button in a template does not stop a
direct POST, and a double-submitted transition must not be audited twice. ``status`` is
``editable=False`` for the same reason.

**This model HAS its own ``tenant`` column**, so every queryset is
``filter(tenant=request.tenant)`` and every object lookup is
``get_object_or_404(..., tenant=request.tenant)`` — never through the invoice alone.

**Import discipline.** Every cross-entity FK below is a STRING (``"procurement.SupplierInvoice"``).
Lane A's module imports two sibling modules at module level, so a class-level import here would
risk a cycle; nothing in this module needs the sibling CLASSES, only the rows.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from apps.procurement.models._base import *  # noqa: F401,F403

#: Ceiling of the money column shape this model writes (DecimalField(14, 2)). A hand-fed
#: ``1e400`` parses as a Decimal and then dies inside the driver, so magnitude is checked BEFORE
#: anything is compared or written (L35).
_MONEY_CEILING = Decimal(10) ** 12

#: The span a date column can actually carry (L35 for dates: a driver rejects a year outside
#: 1000-9999 and every figure derived from a date pair — SLA breach, aging — is only meaningful
#: inside it).
_MIN_DATE = date(1900, 1, 1)
_MAX_DATE = date(9999, 12, 31)


def _finite(value):
    """``value`` as a finite ``Decimal``, or ``None``.

    ``Decimal("nan")`` and ``Decimal("Infinity")`` both PARSE and then raise on the COMPARISON,
    so finiteness is tested before anything else touches the figure.
    """
    try:
        number = Decimal(value if value is not None else ZERO)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    return number if number.is_finite() else None


def _as_decimal(value):
    """``value`` as a usable ``Decimal`` — ``ZERO`` for anything unusable."""
    number = _finite(value)
    return ZERO if number is None else number


REASON_CODE_CHOICES = [("price", "Price Dispute"), ("quantity", "Quantity Dispute"),
                       ("goods_not_received", "Missing Goods"), ("damaged", "Damaged / Quality"),
                       ("duplicate", "Duplicate Invoice"),
                       ("credit_not_processed", "Credit Not Processed"), ("tax", "Tax / VAT Error"),
                       ("freight", "Unapproved Freight or Charges"),
                       ("admin", "Administrative Error"), ("other", "Other")]

RESOLUTION_CHOICES = [("credit_memo", "Supplier Credit Memo"), ("debit_memo", "Debit Memo Raised"),
                      ("reinvoice", "Supplier Re-Invoice"), ("short_pay", "Short Payment Accepted"),
                      ("withdrawn", "Dispute Withdrawn")]

STATUS_CHOICES = [("open", "Open"), ("awaiting_supplier", "Awaiting Supplier"),
                  ("awaiting_internal", "Awaiting Internal Review"), ("resolved", "Resolved"),
                  ("escalated", "Escalated"), ("closed", "Closed")]


class InvoiceDispute(TenantNumbered):
    """A contested part of a supplier invoice [DSP-].

    Lifecycle::

                        +----------------------------------------------+
                        |                                              v
        open -> awaiting_supplier -> awaiting_internal -> escalated -> resolved -> closed

    Every arrow is a verb method below. A dispute is OPEN work from ``open`` through
    ``escalated``; ``resolved`` is the answer; ``closed`` files it. A dispute can also be
    WITHDRAWN straight from any open state, which files it with ``resolution="withdrawn"``
    rather than pretending it was ever answered.

    ``disputed_amount`` is how much of the invoice is held back. It is capped at the invoice
    total — a dispute cannot be worth more than the claim it is against — and
    ``undisputed_balance`` is what remains payable while the argument runs.
    """

    NUMBER_PREFIX = "DSP"

    #: Days a dispute may run before it is late. Set once, on creation, as ``due_date``.
    SLA_DAYS = 10
    #: Every status that is still live work — the complement of resolved/closed.
    OPEN_STATUSES = ("open", "awaiting_supplier", "awaiting_internal", "escalated")

    # -- badge maps (L33) ---------------------------------------------------------------------
    # theme.css defines ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
    # badge-slate. A semantic ``badge-success`` / ``badge-danger`` renders COMPLETELY UNSTYLED.
    STATUS_CSS = {
        "open": "badge-amber",
        "awaiting_supplier": "badge-info",
        "awaiting_internal": "badge-slate",
        "escalated": "badge-red",
        "resolved": "badge-green",
        "closed": "badge-muted",
    }
    REASON_CSS = {
        "price": "badge-amber",
        "quantity": "badge-amber",
        "goods_not_received": "badge-red",
        "damaged": "badge-red",
        "duplicate": "badge-red",
        "credit_not_processed": "badge-info",
        "tax": "badge-slate",
        "freight": "badge-slate",
        "admin": "badge-muted",
        "other": "badge-muted",
    }

    # -- what the dispute is about --------------------------------------------------------------
    invoice = models.ForeignKey("procurement.SupplierInvoice", on_delete=models.CASCADE,
                                related_name="disputes")
    invoice_line = models.ForeignKey("procurement.SupplierInvoiceLine", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="disputes")
    #: Denormalised from ``invoice.vendor`` in ``save()`` — a register row must be readable
    #: without walking the header on every render. Never a form field.
    supplier = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                                 related_name="procurement_invoice_disputes")

    reason_code = models.CharField(max_length=24, choices=REASON_CODE_CHOICES)
    #: Moved ONLY by the verb methods — ``editable=False`` keeps it off every form.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open",
                              editable=False)

    disputed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO,
                                          validators=[MinValueValidator(ZERO)])
    description = models.TextField()
    supplier_contact = models.CharField(max_length=120, blank=True)

    #: Who is chasing it. ``accounts.User.tenant`` is nullable, so ``TenantModelForm`` scopes the
    #: dropdown on its own.
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="procurement_invoice_disputes_assigned")
    due_date = models.DateField(null=True, blank=True)

    # -- audit trail (all stamped, never asked) ---------------------------------------------------
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, blank=True, editable=False,
                                  related_name="procurement_invoice_disputes_raised")
    raised_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)

    # -- the answer ------------------------------------------------------------------------------
    resolution = models.CharField(max_length=16, choices=RESOLUTION_CHOICES, blank=True)
    resolution_note = models.TextField(blank=True)
    #: Set by the resolve view when it mints one — a credit memo is a SUPPLIER INVOICE, not a new
    #: entity, and the link is what makes the settlement auditable in both directions.
    credit_memo_invoice = models.ForeignKey("procurement.SupplierInvoice", on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name="resolved_disputes")

    class Meta:
        ordering = ["-raised_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # Backs the register's status filter and the overdue scan.
            models.Index(fields=["tenant", "status", "due_date"], name="prc_dsp_tnt_status_idx"),
            # Backs the supplier filter and every per-supplier rollup.
            models.Index(fields=["tenant", "supplier"], name="prc_dsp_tnt_supplier_idx"),
        ]
        verbose_name = "invoice dispute"

    def __str__(self):
        return f"{self.number or 'DSP'} · {self.get_reason_code_display()}"

    # -- validation -----------------------------------------------------------------------------

    def clean(self):
        errors = {}
        tenant_id = self.tenant_id
        invoice = self.invoice if self.invoice_id else None

        if invoice is not None and tenant_id and invoice.tenant_id != tenant_id:
            errors["invoice"] = "That invoice belongs to another workspace."
        if self.supplier_id and tenant_id and self.supplier.tenant_id != tenant_id:
            errors["supplier"] = "That supplier belongs to another workspace."

        if self.invoice_line_id and self.invoice_line.invoice_id != self.invoice_id:
            # Otherwise a crafted row argues about a line on a different document, and the
            # dispute then reads as being about goods that invoice never billed.
            errors["invoice_line"] = "That line belongs to a different invoice."

        amount = _finite(self.disputed_amount)
        if amount is None or amount.copy_abs() >= _MONEY_CEILING:
            errors["disputed_amount"] = "Enter a disputed amount below 1,000,000,000,000."
        elif invoice is not None and amount > _as_decimal(invoice.total).copy_abs():
            # ``abs`` because a credit memo's total is negative by design — the size of the claim
            # is what caps the dispute, not its sign.
            errors["disputed_amount"] = (
                "The disputed amount cannot be more than the invoice total.")

        if self.due_date is not None and not (_MIN_DATE <= self.due_date <= _MAX_DATE):
            errors["due_date"] = "Enter a due date between 1900 and 9999."

        if self.credit_memo_invoice_id:
            memo = self.credit_memo_invoice
            if memo.invoice_type != "credit_memo":
                errors["credit_memo_invoice"] = "The credit memo link must point at a credit memo."
            if tenant_id and memo.tenant_id != tenant_id:
                errors["credit_memo_invoice"] = "That invoice belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.invoice_id and self.supplier_id is None:
            self.supplier_id = self.invoice.vendor_id
        if self.due_date is None and not self.pk:
            # Only on CREATE: clearing a typed due date on edit is a deliberate act, and silently
            # re-arming the SLA would hide it.
            self.due_date = timezone.localdate() + timedelta(days=self.SLA_DAYS)
        super().save(*args, **kwargs)

    # -- derived figures -------------------------------------------------------------------------

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def days_open(self):
        """Whole days since the dispute was raised — 0 before ``raised_at`` is stamped."""
        if self.raised_at is None:
            return 0
        return max(0, (timezone.now() - self.raised_at).days)

    @property
    def is_overdue(self):
        """Past its due date AND still live work — a settled dispute is never overdue."""
        return bool(self.due_date and self.due_date < timezone.localdate() and self.is_open)

    @property
    def age_bucket(self):
        """Where this dispute sits on the aging board, in ``AGING_BUCKETS``' vocabulary.

        ``overdue`` wins over the age bands: an aging report exists to surface what is LATE, and
        a three-day-old dispute with a due date that has already passed is the more urgent row.
        """
        if self.due_date is None:
            return "none"
        if self.is_overdue:
            return "overdue"
        days = self.days_open
        if days <= 7:
            return "0-7"
        if days <= 14:
            return "8-14"
        if days <= 30:
            return "15-30"
        if days <= 60:
            return "31-60"
        return "60+"

    @property
    def undisputed_balance(self):
        """What is still payable on the invoice while this dispute runs."""
        if self.invoice_id is None:
            return ZERO
        return q2(_as_decimal(self.invoice.total) - _as_decimal(self.disputed_amount))

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def reason_css(self):
        return self.REASON_CSS.get(self.reason_code, "badge-slate")

    # -- lifecycle verbs -------------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool, and each writes only its
    # own columns through update_fields.

    def await_supplier(self, user):
        """The ball is with the supplier."""
        if self.status not in ("open", "awaiting_internal", "escalated"):
            return False
        self.status = "awaiting_supplier"
        self.save(update_fields=["status", "updated_at"])
        return True

    def await_internal(self, user):
        """The ball is back with us — goods, a GRN, or a decision."""
        if self.status not in ("open", "awaiting_supplier", "escalated"):
            return False
        self.status = "awaiting_internal"
        self.save(update_fields=["status", "updated_at"])
        return True

    def escalate(self, user):
        """Take it above the AP clerk."""
        if self.status not in ("open", "awaiting_supplier", "awaiting_internal"):
            return False
        self.status = "escalated"
        self.save(update_fields=["status", "updated_at"])
        return True

    def resolve(self, user, resolution, note=""):
        """Answer the dispute. Any OPEN state → ``resolved``.

        ``user`` is accepted for symmetry with the other verbs; the actor is recorded by the
        caller's audit row. ``resolution`` must be one of ``RESOLUTION_CHOICES`` — an unknown
        value is refused rather than stored, because a free-text outcome is not reportable.
        """
        if not self.is_open:
            return False
        if resolution not in dict(RESOLUTION_CHOICES):
            return False
        self.status = "resolved"
        self.resolution = resolution
        self.resolution_note = note or ""
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolution", "resolution_note", "resolved_at",
                                 "updated_at"])
        return True

    def close(self, user):
        """File an answered dispute."""
        if self.status != "resolved":
            return False
        self.status = "closed"
        self.save(update_fields=["status", "updated_at"])
        return True

    def withdraw(self, user, note=""):
        """Drop it from any OPEN state — we were wrong, or the supplier conceded in full.

        Recorded as ``resolution="withdrawn"`` so a report can tell a dispute that was ANSWERED
        from one that was ABANDONED.
        """
        if not self.is_open:
            return False
        self.status = "closed"
        self.resolution = "withdrawn"
        self.resolution_note = note or ""
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolution", "resolution_note", "resolved_at",
                                 "updated_at"])
        return True

    def link_credit_memo(self, invoice):
        """Attach the credit memo raised to settle this dispute."""
        if invoice is None or invoice.pk is None:
            return False
        self.credit_memo_invoice = invoice
        self.save(update_fields=["credit_memo_invoice", "updated_at"])
        return True
