"""CPQQuoteLine model representing hierarchical quote lines, bundles, and component items."""
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from apps.sales.models._base import TenantOwned


class CPQQuoteLine(TenantOwned):
    """Line item on a CPQ quote supporting hierarchical bundles, pricing waterfalls, and inventory SKUs."""

    LINE_TYPE_CHOICES = [
        ("standard", "Standard Item"),
        ("bundle_parent", "Bundle Package Header"),
        ("bundle_component", "Bundle Component"),
        ("optional_addon", "Optional Add-on"),
    ]

    quote = models.ForeignKey(
        "sales.CPQQuote",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    parent_line = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bundle_children",
        help_text="Parent line if this is a bundled option component",
    )
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES, default="standard")
    product = models.ForeignKey(
        "crm.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quote_lines",
        help_text="Catalog product reference",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quote_lines",
        help_text="Physical inventory SKU for stock reservation & ERP fulfillment",
    )
    uom = models.ForeignKey(
        "scm.UOM",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quote_lines",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    list_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    tax_code = models.ForeignKey(
        "accounting.TaxCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cpq_quote_lines",
    )
    tax_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Internal unit cost for real-time margin tracking",
    )

    line_subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    line_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    line_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    line_margin = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), editable=False)
    margin_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), editable=False)

    is_optional = models.BooleanField(
        default=False,
        help_text="Can be accepted or declined interactively by customer on portal",
    )
    is_selected = models.BooleanField(
        default=True,
        help_text="Determines whether this line participates in quote calculations",
    )
    sequence = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["sequence", "id"]
        indexes = [
            models.Index(fields=["tenant", "quote"], name="sales_cpqln_tnt_quo_idx"),
            models.Index(fields=["tenant", "parent_line"], name="sales_cpqln_tnt_parent_idx"),
        ]

    def __str__(self):
        return f"{self.quote.number} Line {self.sequence}: {self.description}"
