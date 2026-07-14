"""Accounting 2.3 Accounts Payable — Bills models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ========================================================== 2.3 Accounts Payable
class Bill(TenantNumbered):
    """A vendor AP bill [BILL-]. Approval-routed; totals recomputed from lines."""

    NUMBER_PREFIX = "BILL"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]
    OPEN_STATUSES = ("approved", "partial")

    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="accounting_bills")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="bills")
    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="bills")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="bills", editable=False)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="accounting_bills_approved", editable=False)
    document = models.ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="accounting_bills", help_text="Scanned bill attachment")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-bill_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_bill_tenant_status_idx")]

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
        return self.allocations.filter(payment__status="confirmed").aggregate(
            s=Sum("allocated_amount"))["s"] or ZERO

    def balance_due(self):
        return self.total - self.amount_paid()

    def recompute_payment_status(self):
        """Derive approved/partial/paid from confirmed allocations (security review H1)."""
        if self.status in ("draft", "pending_approval", "void"):
            return
        paid = self.amount_paid()
        new = "paid" if (self.total > ZERO and paid >= self.total) else ("partial" if paid > ZERO else "approved")
        if new != self.status:
            self.status = new
            self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return self.number or f"BILL #{self.pk}"


class BillLine(models.Model):
    bill = models.ForeignKey("accounting.Bill", on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="bill_lines", help_text="Expense account")

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or ZERO) * (self.unit_price or ZERO)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description
