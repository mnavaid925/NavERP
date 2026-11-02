from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.ecommerce.models._base import TenantNumbered


class B2bQuoteRequest(TenantNumbered):
    NUMBER_PREFIX = "EBQR"

    STATUS_CHOICES = [
        ("draft", "Draft (Preparing RFQ)"),
        ("submitted", "Submitted / Pending Review"),
        ("under_review", "Under Review"),
        ("quoted", "Quoted / Offer Sent"),
        ("buyer_review", "Buyer Review"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("converted_to_order", "Converted to Order"),
    ]

    company = models.ForeignKey(
        "ecommerce.B2bCompanyAccount",
        on_delete=models.CASCADE,
        related_name="quote_requests",
        help_text="Wholesale company requesting quote",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_b2b_quotes",
        help_text="Company buyer submitting quote request",
    )
    assigned_sales_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_b2b_quotes",
        help_text="Internal wholesale account executive handling negotiation",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="b2b_quote_requests",
        help_text="Quotation settlement currency",
    )
    converted_order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_b2b_quotes",
        help_text="Order generated from this quote upon buyer acceptance",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Negotiation lifecycle status",
    )
    target_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Buyer target budget ceiling",
    )
    original_subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Standard catalog price subtotal before negotiated discounts",
    )
    quoted_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Custom negotiated percentage discount granted",
    )
    quoted_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Formal final quoted price offered to buyer",
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated applicable sales/VAT tax",
    )
    shipping_estimate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated freight or delivery charges",
    )
    target_delivery_date = models.DateField(
        null=True,
        blank=True,
        help_text="Requested delivery date by buyer",
    )
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Proposal expiration date/time",
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when buyer submitted RFQ",
    )
    quoted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when merchant offer was dispatched",
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when buyer accepted proposal",
    )
    line_items_data = models.JSONField(
        default=list,
        blank=True,
        help_text="List of items: product_id, sku, name, requested_qty, requested_unit_price, quoted_unit_price, line_total, notes",
    )
    buyer_notes = models.TextField(
        blank=True,
        default="",
        help_text="Special instructions and requirements from customer",
    )
    merchant_notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal margin calculation and pricing notes",
    )
    rejection_reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason recorded if quote was declined",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_ebqr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_ebqr_ten_created"),
            models.Index(fields=["tenant", "company", "status"], name="idx_ebqr_ten_co_stat"),
            models.Index(fields=["tenant", "status"], name="idx_ebqr_ten_stat"),
            models.Index(fields=["tenant", "company"], name="idx_ebqr_ten_co"),
            models.Index(fields=["tenant", "valid_until"], name="idx_ebqr_ten_valid"),
        ]

    def __str__(self):
        return f"Quote {self.number} - {self.company.company_name} ({self.status})"

    def recalculate_totals(self):
        """Recalculate subtotal and quoted total from line items and discounts."""
        if self.line_items_data:
            subtotal = Decimal("0.00")
            for item in self.line_items_data:
                qty = Decimal(str(item.get("requested_qty", 1)))
                unit_price = Decimal(str(item.get("quoted_unit_price") or item.get("requested_unit_price") or 0))
                line_tot = (qty * unit_price).quantize(Decimal("0.01"))
                item["line_total"] = float(line_tot)
                subtotal += line_tot
            self.original_subtotal = subtotal
        else:
            subtotal = self.original_subtotal or Decimal("0.00")

        if self.quoted_discount_percent and self.quoted_discount_percent > Decimal("0.00"):
            disc_factor = Decimal("1.00") - (self.quoted_discount_percent / Decimal("100.00"))
            discounted = (subtotal * disc_factor).quantize(Decimal("0.01"))
        else:
            discounted = subtotal

        self.quoted_total = (discounted + self.tax_amount + self.shipping_estimate).quantize(Decimal("0.01"))
        return self.quoted_total
