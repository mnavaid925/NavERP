"""Accounting 2.4 Accounts Receivable — Invoices models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ======================================================= 2.4 Accounts Receivable
class Invoice(TenantNumbered):
    """A customer AR invoice (or credit note) [INV-]. Totals are recomputed from lines."""

    NUMBER_PREFIX = "INV"

    KIND_CHOICES = [("invoice", "Invoice"), ("credit_note", "Credit Note")]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]
    OPEN_STATUSES = ("sent", "partial")

    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="invoice")
    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="accounting_invoices")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="invoices")
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="invoices")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="invoices", editable=False)
    recurring_invoice = models.ForeignKey("accounting.RecurringInvoice", on_delete=models.SET_NULL, null=True,
                                          blank=True, related_name="generated_invoices", editable=False,
                                          help_text="The schedule that generated this invoice, if any.")
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_inv_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status in ("paid", "void")

    def recalc_totals(self, save=True):
        rows = list(self.lines.all())
        subtotal = sum((r.line_total for r in rows), ZERO)
        tax = sum(((r.line_total * (r.tax_rate_pct or ZERO) / 100) for r in rows), ZERO)
        self.subtotal, self.tax_total, self.total = subtotal, tax, subtotal + tax
        if save:
            self.save(update_fields=["subtotal", "tax_total", "total", "updated_at"])

    def amount_paid(self):
        # Only confirmed payments count toward the balance — a voided payment's allocation
        # must not keep an invoice marked paid.
        return self.allocations.filter(payment__status="confirmed").aggregate(
            s=Sum("allocated_amount"))["s"] or ZERO

    def balance_due(self):
        return self.total - self.amount_paid()

    def recompute_payment_status(self):
        """Derive sent/partial/paid from confirmed allocations. Status is NOT user-editable on the
        form — it advances here (and via ``invoice_post``), never by hand (security review H1)."""
        if self.status in ("draft", "void"):
            return
        paid = self.amount_paid()
        new = "paid" if (self.total > ZERO and paid >= self.total) else ("partial" if paid > ZERO else "sent")
        if new != self.status:
            self.status = new
            self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return self.number or f"INV #{self.pk}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="invoice_lines", help_text="Income / revenue account")

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or ZERO) * (self.unit_price or ZERO)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description
