"""SCM 4.1 Procurement Management — RFQ models.

An RFQ is issued to several suppliers at once; each returns an ``RFQQuote`` whose lines price the
RFQ's lines. Quotes are children of the RFQ (they have no life of their own) so they live in this
entity module per the Backend Package Structure rule.

Item references stay free-text until ``core.Item`` lands with Module 5 (lesson L28).
"""
from apps.scm.models._base import *  # noqa: F401,F403


class RFQ(TenantNumbered):
    """A Request For Quotation issued to one or more suppliers [RFQ-]."""

    NUMBER_PREFIX = "RFQ"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("closed", "Closed"),
        ("awarded", "Awarded"),
        ("cancelled", "Cancelled"),
    ]
    EDITABLE_STATUSES = ("draft", "sent")

    title = models.CharField(max_length=255)
    requisition = models.ForeignKey("scm.PurchaseRequisition", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="rfqs", help_text="Requisition this RFQ sources")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_rfqs")
    issue_date = models.DateField(null=True, blank=True)
    response_due = models.DateField(null=True, blank=True, help_text="Deadline for supplier responses")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    terms = models.TextField(blank=True, help_text="Terms & conditions sent to suppliers")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_rfq_tenant_status_idx"),
        ]

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    def awarded_quote(self):
        return self.quotes.filter(status="awarded").first()

    def __str__(self):
        return f"{self.number or 'RFQ'} · {self.title}"


class RFQLine(models.Model):
    """One item the RFQ asks suppliers to price."""

    rfq = models.ForeignKey("scm.RFQ", on_delete=models.CASCADE, related_name="lines")
    item_description = models.CharField(max_length=255)
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField(max_length=32, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    specification = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.item_description} ×{self.quantity}"


class RFQVendor(models.Model):
    """A supplier invited to quote on this RFQ.

    Tenant-scoped in its own right (not just via the RFQ) so the invite list can be filtered and
    audited directly, consistent with how the other child tables are queried.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    rfq = models.ForeignKey("scm.RFQ", on_delete=models.CASCADE, related_name="invited_vendors")
    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="scm_rfq_invites")
    invited_at = models.DateTimeField(null=True, blank=True)
    contact_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["party__name"]
        unique_together = ("rfq", "party")

    @property
    def has_responded(self):
        return self.rfq.quotes.filter(party_id=self.party_id).exists()

    def __str__(self):
        return f"{self.party} on {self.rfq_id}"


class RFQQuote(TenantNumbered):
    """A supplier's response to an RFQ [QT-]. ``total`` is recomputed from lines."""

    NUMBER_PREFIX = "QT"

    STATUS_CHOICES = [
        ("received", "Received"),
        ("shortlisted", "Shortlisted"),
        ("awarded", "Awarded"),
        ("rejected", "Rejected"),
    ]

    rfq = models.ForeignKey("scm.RFQ", on_delete=models.CASCADE, related_name="quotes")
    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="scm_quotes")
    vendor_reference = models.CharField(max_length=64, blank=True, help_text="The supplier's own quote number")
    received_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True,
                                                 help_text="Quoted delivery lead time, in days")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="scm_quotes")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="received")
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["total", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_quote_tnt_status_idx"),
        ]

    def recalc_totals(self, save=True):
        self.total = sum((r.line_total for r in self.lines.all()), ZERO)
        if save:
            self.save(update_fields=["total", "updated_at"])

    def __str__(self):
        return f"{self.number or 'QT'} · {self.party}"


class RFQQuoteLine(models.Model):
    """A supplier's price for one RFQ line. ``line_total`` is derived."""

    quote = models.ForeignKey("scm.RFQQuote", on_delete=models.CASCADE, related_name="lines")
    rfq_line = models.ForeignKey("scm.RFQLine", on_delete=models.CASCADE, related_name="quote_lines")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)])
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["rfq_line_id", "id"]
        unique_together = ("quote", "rfq_line")

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or ZERO) * (self.unit_price or ZERO)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rfq_line_id} @ {self.unit_price}"
