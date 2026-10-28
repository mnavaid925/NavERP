"""SalesPriceBookEntry model for 8.19 Master Data & Configuration — Product Catalog & Pricing."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered


class SalesPriceBookEntry(TenantNumbered):
    """Concrete junction linking crm.PriceBook and crm.Product/scm.Item with granular pricing terms."""

    NUMBER_PREFIX = "PBE"

    PRICING_MODEL_CHOICES = [
        ("flat", "Flat Unit Price"),
        ("tier_volume", "Volume Tier Discount"),
        ("tier_graduated", "Graduated / Bracket Pricing"),
        ("cost_markup", "Cost-Plus Markup"),
    ]

    price_book = models.ForeignKey(
        "crm.PriceBook",
        on_delete=models.CASCADE,
        related_name="sales_entries",
        help_text="Target commercial price book header",
    )
    product = models.ForeignKey(
        "crm.Product",
        on_delete=models.CASCADE,
        related_name="sales_price_book_entries",
        help_text="Commercial product catalog item",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_price_book_entries",
        help_text="Physical inventory SKU link for warehouse fulfillment",
    )
    sku_code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Distributor or manufacturer SKU code",
    )
    currency_code = models.CharField(
        max_length=3,
        default="USD",
        help_text="ISO 4217 commercial currency code (e.g. USD, EUR, GBP)",
    )
    list_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Standard unit price before volume discounts",
    )
    floor_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Minimum allowable floor price to protect margin",
    )
    pricing_model = models.CharField(
        max_length=20,
        choices=PRICING_MODEL_CHOICES,
        default="flat",
        help_text="Algorithmic pricing calculation model",
    )
    min_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Minimum order quantity (MOQ) required for this price",
    )
    volume_tier_breaks = models.JSONField(
        default=list,
        blank=True,
        help_text="Tier brackets formatted as [{'min_qty': 10, 'discount_pct': 5.0, 'unit_price': 95.0}]",
    )
    valid_from = models.DateField(
        null=True,
        blank=True,
        help_text="Effective start date of pricing availability",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        help_text="Expiration date of pricing terms",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this pricing entry is active for quotes and orders",
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal pricing notes, concessions, or contractual terms",
    )

    class Meta:
        ordering = ["price_book", "product", "currency_code", "-is_active"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_pbe_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "price_book", "product", "currency_code"],
                name="sales_pbe_bk_prd_cur_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="sales_pbe_tnt_act_idx"),
            models.Index(fields=["tenant", "sku_code"], name="sales_pbe_sku_idx"),
            models.Index(fields=["tenant", "currency_code"], name="sales_pbe_curr_idx"),
            models.Index(fields=["tenant", "price_book", "is_active"], name="sales_pbe_pb_act_idx"),
        ]

    def clean(self):
        super().clean()
        if self.price_book_id and self.price_book.tenant_id != self.tenant_id:
            raise ValidationError({"price_book": "Price book must belong to the active workspace."})
        if self.product_id and self.product.tenant_id != self.tenant_id:
            raise ValidationError({"product": "Product must belong to the active workspace."})
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "Inventory item must belong to the active workspace."})
        if self.floor_price is not None and self.list_price is not None:
            if self.floor_price > self.list_price:
                raise ValidationError({"floor_price": "Floor price cannot exceed list price."})
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValidationError({"valid_to": "Expiration date cannot precede effective start date."})
        if not isinstance(self.volume_tier_breaks, list):
            raise ValidationError({"volume_tier_breaks": "Volume tier breaks must be a JSON array."})

    def __str__(self):
        return f"{self.number} · {self.price_book.name} - {self.product.name} ({self.currency_code} {self.list_price})"
