"""Inventory 5.1 Product & Catalog Management — ItemPrice.

**Pricing & Costing** bullet: retail price, wholesale price and price breaks as SELL-SIDE rows on
the catalog spine. The COST side already lives on 4.3's ``scm.Item`` (``standard_cost`` plus the
derived ``average_cost`` maintained by the receipt/landed-cost writers), which is exactly why this
table stores no cost column of its own — a second cost figure beside ``standard_cost`` would be two
sources of truth for the same fact (L37's reasoning, applied to money instead of ownership).

Rows, not columns, because a SKU legitimately carries SEVERAL live prices at once: a wholesale
break at 10+ units, another at 50+, a dated promotional window. One row per (type, break, window)
expresses all of it without widening the shared master.

``margin_pct`` / ``markup_pct`` are computed against the item's CURRENT ``standard_cost``, never
stored — repricing the cost must not silently reprice history.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class ItemPrice(TenantOwned):
    """One sell-side price row for a product — a type, an amount, optionally a break and a window."""

    PRICE_TYPE_CHOICES = [
        ("retail", "Retail"),
        ("wholesale", "Wholesale"),
        ("promotional", "Promotional"),
        ("clearance", "Clearance"),
    ]

    item = models.ForeignKey(
        "scm.Item", on_delete=models.CASCADE, related_name="catalog_prices",
        help_text="The product being priced")
    price_type = models.CharField(max_length=12, choices=PRICE_TYPE_CHOICES, default="retail")
    unit_price = models.DecimalField(max_digits=14, decimal_places=4,
                                     validators=[MinValueValidator(ZERO)])
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="+",
                                 help_text="Blank = the workspace default currency")
    min_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=1,
                                       validators=[MinValueValidator(ZERO)],
                                       help_text="Price-break threshold; 1 = the base price")
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True,
                                   help_text="Open-ended when blank")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item_id", "price_type", "min_quantity"]
        indexes = [
            models.Index(fields=["tenant", "item"], name="inv_prp_tnt_item_idx"),
            models.Index(fields=["tenant", "price_type"], name="inv_prp_tnt_type_idx"),
        ]

    def clean(self):
        errors = {}
        if self.item_id and self.item.tenant_id != self.tenant_id:
            errors["item"] = "That item belongs to another workspace."
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            errors["valid_until"] = "The window cannot end before it starts."
        if errors:
            raise ValidationError(errors)

    def covers(self, on_date):
        """True when this row applies on ``on_date`` — an open end stays open."""
        if self.valid_from and on_date < self.valid_from:
            return False
        if self.valid_until and on_date > self.valid_until:
            return False
        return True

    @property
    def margin_pct(self):
        """(price − standard_cost) / price × 100 — ``None`` at a zero or missing cost basis."""
        cost = self.item.standard_cost if self.item_id else ZERO
        price = self.unit_price or ZERO
        if price <= ZERO or cost is None:
            return None
        return ((price - cost) / price * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def markup_pct(self):
        """(price − standard_cost) / standard_cost × 100 — ``None`` while the cost basis is zero.

        A zero-cost markup is undefined (division by zero), not 0 %: saying "0 %" would read as
        "priced at cost", the one thing a zero cost basis cannot tell you.
        """
        cost = self.item.standard_cost if self.item_id else ZERO
        price = self.unit_price or ZERO
        if cost <= ZERO:
            return None
        return ((price - cost) / cost * Decimal("100")).quantize(Decimal("0.01"))

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{sku} · {self.get_price_type_display()} {self.unit_price}"
