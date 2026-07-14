"""CRM 1.2 Sales Force Automation — Quotes models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Quote(TenantNumbered):
    """A sales quote (1.2 Quoting) with line items, per-line + quote-level discount and tax.
    ``status`` and the ``subtotal``/``tax_total``/``total`` + ``sent_at``/``accepted_at`` are
    SYSTEM-managed (set by the send/accept/decline actions + ``recalc_totals()``) and excluded
    from the form, so a user can't forge a total or self-accept a quote via POST."""

    NUMBER_PREFIX = "QUO"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired", "Expired"),
    ]
    OPEN_STATUSES = ("draft", "sent")

    name = models.CharField(max_length=255)
    opportunity = models.ForeignKey("Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_quotes")
    price_book = models.ForeignKey("PriceBook", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    valid_until = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="USD")
    discount_pct = models.DecimalField(  # quote-level, on top of line discounts
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # system (recalc_totals)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # system
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)      # system
    sent_at = models.DateTimeField(null=True, blank=True)      # system (quote_send)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system (quote_accept)
    terms = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_quotes")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_quo_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_quo_tnt_created_idx"),
        ]

    def recalc_totals(self, save=True):
        """Recompute subtotal/tax/total from the lines, then apply the quote-level discount.
        Lines store unit_price/discount/tax; totals are derived, never user-entered.

        Summed in Python over the (few, bounded) lines using the Decimal-safe line properties —
        NOT a DB-side ``F()/100`` expression, which integer-divides on SQLite and silently drops
        per-line discounts/tax. One query (``self.lines.all()``); quotes have a handful of lines."""
        line_sub = Decimal(0)
        line_tax = Decimal(0)
        for ln in self.lines.all():
            line_sub += ln.line_subtotal
            line_tax += ln.line_tax
        disc = (Decimal(100) - Decimal(self.discount_pct or 0)) / 100  # quote-level discount factor
        # The discount factor is applied to BOTH subtotal and tax, so tax is effectively computed
        # on the discounted base (tax_total = line_sub*tax_pct*disc = discounted_subtotal*tax_pct).
        self.subtotal = (line_sub * disc).quantize(Decimal("0.01"))
        self.tax_total = (line_tax * disc).quantize(Decimal("0.01"))
        self.total = (self.subtotal + self.tax_total).quantize(Decimal("0.01"))
        if save:
            super().save(update_fields=["subtotal", "tax_total", "total", "updated_at"])

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_expired(self):
        return bool(self.valid_until and self.status in self.OPEN_STATUSES
                    and self.valid_until < timezone.localdate())

    def __str__(self):
        return f"{self.number} · {self.name}"


class QuoteLine(models.Model):
    """A line item on a Quote (1.2). Plain tenant-scoped child; ``line_total`` is a derived
    property (never stored/forged). ``product`` is nullable for free-text write-in lines."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    quote = models.ForeignKey("Quote", on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1,
                                   validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                       validators=[MinValueValidator(0), MaxValueValidator(100)])
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0), MaxValueValidator(100)])
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["tenant", "quote"], name="crm_qline_tnt_quote_idx"),
        ]

    @property
    def line_subtotal(self):
        return (Decimal(self.quantity or 0) * Decimal(self.unit_price or 0)
                * (Decimal(1) - Decimal(self.discount_pct or 0) / 100))

    @property
    def line_tax(self):
        return self.line_subtotal * Decimal(self.tax_pct or 0) / 100

    @property
    def line_total(self):
        return self.line_subtotal + self.line_tax

    def __str__(self):
        return f"{self.description} × {self.quantity}"
