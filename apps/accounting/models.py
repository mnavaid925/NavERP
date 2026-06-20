"""Accounting & Finance (Module 2) domain models — the GL ledger spine.

**Architecture (lesson L28).** The unified-core spine (`apps/core`) does NOT yet contain a
financial ledger — there is no `GLAccount`, `JournalEntry`, `Currency`, `Invoice`, `Payment`
or `BankAccount` in core. Module 2 / `apps.accounting` therefore BUILDS that spine itself and
OWNS it; later modules (Inventory, Procurement, Sales, Assets) FK into ``accounting.*`` by
string, exactly as every module FKs into ``core.*`` by string.

What this app reuses from the confirmed-existing core spine:
  * ``core.Party`` / ``core.PartyRole`` — vendors & customers are *roles on a Party*, never new
    tables (``VendorProfile`` / ``CustomerProfile`` are thin OneToOne extensions only).
  * ``core.OrgUnit`` — GL cost-centre dimension on a journal line.
  * ``core.Document`` — scanned-bill attachment.
  * ``core.utils.next_number`` / ``write_audit_log`` and ``core.decorators.tenant_admin_required``.

Double-entry invariants (enforced at the model + view layer):
  1. A ``JournalEntry`` may not be *posted* unless ``sum(debit) == sum(credit)`` (and > 0).
  2. A posted/void ``JournalEntry`` is immutable — corrections are a *reversal* entry
     (``reversal_of``). Edit/delete are gated in the view via :pyattr:`JournalEntry.is_locked`.
  3. A ``GLAccount`` has **no stored balance** — it is always derived by aggregating *posted*
     ``JournalLine`` rows (:pymeth:`GLAccount.balance`).
  4. Posting into a non-open ``FiscalPeriod`` is blocked at the view layer.
  5. ``Invoice``/``Bill`` ``subtotal``/``tax_total``/``total`` are recomputed from line items
     (:pymeth:`recalc_totals`), never hand-edited on the ModelForm.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Sum

from apps.core.utils import next_number

ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Shared abstract bases (mirror the proven apps/crm pattern; local copy — peer
# apps don't import each other).
# ---------------------------------------------------------------------------
class TenantOwned(models.Model):
    """Tenant FK + created/updated timestamps. ``related_name="+"`` — views always filter
    ``Model.objects.filter(tenant=request.tenant)`` so no reverse accessor is needed and the
    abstract base never clashes across its many subclasses."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantNumbered(TenantOwned):
    """Adds a human-readable per-tenant ``number`` (e.g. ``JE-00001``) assigned once in
    ``save()`` with a retry-on-collision guard (mirrors ``tenants.SubscriptionInvoice``)."""

    NUMBER_PREFIX = ""

    number = models.CharField(max_length=20, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.number and self.tenant_id and self.NUMBER_PREFIX:
            for _ in range(5):
                self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    self.number = ""
        return super().save(*args, **kwargs)


# =========================================================== 2.2 General Ledger
class Currency(models.Model):
    """ISO 4217 currency master. **Global** — shared across all tenants (no tenant FK), exactly
    as the intended ERD treats currencies as a shared reference master."""

    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=60)
    symbol = models.CharField(max_length=8, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self):
        return self.code


class ExchangeRate(TenantOwned):
    """Daily spot rate for a currency (functional currency assumed = tenant base)."""

    SOURCE_CHOICES = [("manual", "Manual"), ("feed", "Feed")]

    currency = models.ForeignKey("accounting.Currency", on_delete=models.CASCADE, related_name="exchange_rates")
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["-rate_date", "currency__code"]
        unique_together = ("tenant", "currency", "rate_date")
        indexes = [models.Index(fields=["tenant", "rate_date"], name="acc_fx_tenant_date_idx")]

    def __str__(self):
        return f"{self.currency_id and self.currency.code} @ {self.rate} ({self.rate_date})"


class GLAccount(TenantOwned):
    """A Chart-of-Accounts node. Hierarchical (``parent``), typed, and **never** stores a
    balance — :pymeth:`balance` aggregates posted journal lines on demand (invariant 3)."""

    ACCOUNT_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    ]
    NORMAL_BALANCE_CHOICES = [("debit", "Debit"), ("credit", "Credit")]
    DEBIT_NORMAL_TYPES = ("asset", "expense")

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=12, choices=ACCOUNT_TYPE_CHOICES)
    # Derived from account_type in save() — read-only, never on the ModelForm.
    normal_balance = models.CharField(max_length=6, choices=NORMAL_BALANCE_CHOICES, editable=False, default="debit")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "is_active"], name="acc_gl_tenant_active_idx")]

    def save(self, *args, **kwargs):
        self.normal_balance = "debit" if self.account_type in self.DEBIT_NORMAL_TYPES else "credit"
        super().save(*args, **kwargs)

    def balance(self):
        """Signed balance in the account's *normal* direction over **posted** lines only."""
        agg = self.journal_lines.filter(entry__status="posted").aggregate(d=Sum("debit"), c=Sum("credit"))
        debit, credit = agg["d"] or ZERO, agg["c"] or ZERO
        return (debit - credit) if self.normal_balance == "debit" else (credit - debit)

    def __str__(self):
        return f"{self.code} · {self.name}"


class FiscalPeriod(TenantOwned):
    """An accounting period. Posting is blocked once it is anything other than ``open``."""

    PERIOD_TYPE_CHOICES = [("month", "Month"), ("quarter", "Quarter"), ("year", "Year")]
    STATUS_CHOICES = [("open", "Open"), ("closed", "Closed"), ("locked", "Locked")]

    name = models.CharField(max_length=60)
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPE_CHOICES, default="month")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="accounting_periods_closed", editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["tenant", "status"], name="acc_period_tenant_status_idx")]

    @property
    def is_open(self):
        return self.status == "open"

    def __str__(self):
        return self.name


class JournalEntry(TenantNumbered):
    """Double-entry header [JE-]. Immutable once posted/void (:pyattr:`is_locked`)."""

    NUMBER_PREFIX = "JE"
    LOCKED_STATUSES = ("posted", "void")

    ENTRY_TYPE_CHOICES = [
        ("manual", "Manual"),
        ("invoice", "Invoice Posting"),
        ("payment", "Payment"),
        ("bank", "Bank"),
        ("recurring", "Recurring"),
        ("reversal", "Reversal"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("posted", "Posted"),
        ("void", "Void"),
    ]

    entry_type = models.CharField(max_length=12, choices=ENTRY_TYPE_CHOICES, default="manual")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    fiscal_period = models.ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="journal_entries")
    entry_date = models.DateField()
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="External document reference, e.g. a PO number")
    reversal_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reversals",
                                    editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="accounting_je_created", editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="accounting_je_approved", editable=False)
    posted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-entry_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="acc_je_tenant_status_idx"),
            models.Index(fields=["tenant", "entry_date"], name="acc_je_tenant_date_idx"),
        ]

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    def totals(self):
        agg = self.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        return agg["d"] or ZERO, agg["c"] or ZERO

    def is_balanced(self):
        debit, credit = self.totals()
        return debit == credit and debit > ZERO

    def __str__(self):
        return self.number or f"JE #{self.pk}"


class JournalLine(models.Model):
    """One debit-or-credit arm of a :class:`JournalEntry`. Tenant is inherited from the parent
    entry (child table — no own tenant FK, mirrors CLAUDE.md's join-table exception)."""

    entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.CASCADE, related_name="lines")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="accounting_je_lines")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="accounting_je_lines")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="je_lines")
    amount_foreign = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["gl_account"], name="acc_jline_account_idx")]

    def clean(self):
        # A line is exactly one of debit OR credit — never both, never neither.
        d, c = self.debit or ZERO, self.credit or ZERO
        if d and c:
            raise ValidationError("A journal line cannot have both a debit and a credit amount.")
        if not d and not c:
            raise ValidationError("A journal line must have either a debit or a credit amount.")

    def __str__(self):
        return f"{self.gl_account_id and self.gl_account.code}: Dr {self.debit} / Cr {self.credit}"


# ======================================== 2.3 AP + 2.4 AR shared masters
class PaymentTerm(TenantOwned):
    """Reusable Net-N / early-discount term (e.g. "2/10 Net 30")."""

    name = models.CharField(max_length=80)
    days_due = models.PositiveSmallIntegerField(default=30)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_days = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class VendorProfile(TenantOwned):
    """Thin AP extension on a ``core.Party`` (the vendor). One per Party per workspace."""

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="vendor_profile")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="vendor_profiles")
    default_expense_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                                related_name="vendor_default_expense")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="vendor_profiles")
    is_1099 = models.BooleanField(default=False, verbose_name="1099/W-9 vendor")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["party__name"]

    def __str__(self):
        return f"Vendor: {self.party_id and self.party.name}"


class CustomerProfile(TenantOwned):
    """Thin AR extension on a ``core.Party`` (the customer) with credit controls."""

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="customer_profile")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="customer_profiles")
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ar_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="customer_ar_accounts")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="customer_profiles")
    credit_on_hold = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["party__name"]

    def __str__(self):
        return f"Customer: {self.party_id and self.party.name}"


# ============================================================ 2.5 Cash (defined
# before Payment because Payment FKs a BankAccount).
class BankAccount(TenantOwned):
    """A tenant bank account; the anchor for cash positioning and reconciliation."""

    name = models.CharField(max_length=255)
    account_number_last4 = models.CharField(max_length=4, blank=True, help_text="Last 4 digits only — never store the full number")
    bank_name = models.CharField(max_length=255, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="bank_accounts")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="bank_accounts", help_text="The GL cash account this bank maps to")
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    opening_balance_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def current_balance(self):
        agg = self.transactions.aggregate(
            credit=Sum("amount", filter=Q(direction="credit")),
            debit=Sum("amount", filter=Q(direction="debit")),
        )
        return (self.opening_balance or ZERO) + (agg["credit"] or ZERO) - (agg["debit"] or ZERO)

    def __str__(self):
        return self.name


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


# =================================================== 2.3+2.4 shared Payment + cash application
class Payment(TenantNumbered):
    """A unified inbound (customer receipt) / outbound (vendor payment) money movement [PAY-]."""

    NUMBER_PREFIX = "PAY"

    DIRECTION_CHOICES = [("in", "Inbound — Customer Receipt"), ("out", "Outbound — Vendor Payment")]
    METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("check", "Check"),
        ("cash", "Cash"),
        ("card", "Card"),
        ("ach", "ACH"),
        ("wire", "Wire Transfer"),
    ]
    STATUS_CHOICES = [("draft", "Draft"), ("confirmed", "Confirmed"), ("void", "Void")]

    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="accounting_payments")
    bank_account = models.ForeignKey("accounting.BankAccount", on_delete=models.PROTECT, related_name="payments")
    payment_method = models.CharField(max_length=16, choices=METHOD_CHOICES, default="bank_transfer")
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="payments")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="payments", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_pay_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status in ("confirmed", "void")

    def allocated_total(self):
        return self.allocations.aggregate(s=Sum("allocated_amount"))["s"] or ZERO

    def unallocated(self):
        return (self.amount or ZERO) - self.allocated_total()

    def __str__(self):
        return self.number or f"PAY #{self.pk}"


class PaymentAllocation(models.Model):
    """Cash-application join: applies part of a :class:`Payment` to an Invoice (AR) or Bill (AP).
    Tenant is inherited from ``payment`` (child table)."""

    payment = models.ForeignKey("accounting.Payment", on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="allocations")
    bill = models.ForeignKey("accounting.Bill", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="allocations")
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2)
    discount_taken = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def clean(self):
        # Apply to exactly one document.
        if bool(self.invoice_id) == bool(self.bill_id):
            raise ValidationError("Allocate to exactly one of an invoice or a bill.")

    def __str__(self):
        target = self.invoice_id and self.invoice or self.bill_id and self.bill
        return f"{self.allocated_amount} → {target}"


# =============================================================== 2.5 Bank txns + reconciliation
class BankTransaction(TenantOwned):
    """An imported / fed / manual bank-statement line awaiting reconciliation."""

    DIRECTION_CHOICES = [("credit", "Credit — Money In"), ("debit", "Debit — Money Out")]
    SOURCE_CHOICES = [("manual", "Manual Entry"), ("csv_import", "CSV Import"), ("bank_feed", "Bank Feed")]
    STATUS_CHOICES = [
        ("unmatched", "Unmatched"),
        ("matched", "Matched"),
        ("reconciled", "Reconciled"),
        ("excluded", "Excluded"),
    ]

    bank_account = models.ForeignKey("accounting.BankAccount", on_delete=models.CASCADE, related_name="transactions")
    transaction_date = models.DateField()
    description = models.CharField(max_length=512)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    direction = models.CharField(max_length=6, choices=DIRECTION_CHOICES)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="manual")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="unmatched", editable=False)
    external_ref = models.CharField(max_length=255, blank=True, help_text="Bank's own transaction id (dedupe key)")

    class Meta:
        ordering = ["-transaction_date", "-id"]
        indexes = [models.Index(fields=["tenant", "transaction_date"], name="acc_bt_tenant_date_idx")]

    def __str__(self):
        return f"{self.transaction_date} · {self.description[:40]}"


class ReconciliationMatch(TenantOwned):
    """A confirmed pairing of a :class:`BankTransaction` with a Payment or JournalLine."""

    bank_transaction = models.ForeignKey("accounting.BankTransaction", on_delete=models.CASCADE, related_name="matches")
    payment = models.ForeignKey("accounting.Payment", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="reconciliation_matches")
    journal_line = models.ForeignKey("accounting.JournalLine", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="reconciliation_matches")
    matched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="accounting_reconciliation_matches", editable=False)
    matched_at = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-matched_at"]

    def __str__(self):
        return f"Match #{self.pk} · {self.bank_transaction_id}"


# Advanced sub-modules 2.6–2.15 live in models_advanced.py (Fixed Assets, Cost Allocation,
# Payroll, Job Costing, Intercompany, Tax, Scheduled Reports, Budgeting, Controls, Integration).
# Imported here so Django registers them under the `accounting` app label.
from .models_advanced import *  # noqa: E402,F401,F403
