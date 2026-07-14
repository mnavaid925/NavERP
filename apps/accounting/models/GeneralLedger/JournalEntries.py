"""Accounting 2.2 General Ledger — JournalEntries models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


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
