from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ProductVariant(TenantNumbered):
    """Purchasable SKU configuration matrix with structured options, pricing, and fulfillment anchor."""

    NUMBER_PREFIX = "PVR"

    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="variants",
        help_text="Parent catalog product",
    )
    sku = models.CharField(max_length=64, help_text="Unique stock-keeping unit")
    name = models.CharField(max_length=255, help_text="Variant label, e.g. Medium / Charcoal")
    option_values = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON dictionary of attribute dimensions, e.g. {"Size": "M", "Color": "Charcoal"}',
    )
    barcode = models.CharField(max_length=64, blank=True, help_text="UPC, EAN, or ISBN barcode")
    price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Active storefront selling price",
    )
    compare_at_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Strike-through list price / MSRP",
    )
    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Base item cost for margin computation",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_variants",
        help_text="Physical inventory stock-keeping master for warehouse fulfillment",
    )
    weight_kg = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=Decimal("0.000"),
        validators=[MinValueValidator(Decimal("0.000"))],
        help_text="Shipping weight in kilograms",
    )
    image_url = models.URLField(blank=True, help_text="Variant-specific photo URL")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "sku"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_pvr_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "sku"], name="ecommerce_pvr_tenant_sku_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "product", "is_active"], name="ecom_pvr_tnt_prd_act_idx"),
            models.Index(fields=["tenant", "barcode"], name="ecom_pvr_tnt_barc_idx"),
        ]

    def clean(self):
        super().clean()
        if self.product_id and self.product.tenant_id != self.tenant_id:
            raise ValidationError({"product": "Product must belong to the same workspace."})
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "Inventory item must belong to the same workspace."})
        if not isinstance(self.option_values, dict):
            raise ValidationError({"option_values": "Option values must be a JSON dictionary of key-value pairs."})

    @property
    def is_on_sale(self):
        return bool(self.compare_at_price and self.compare_at_price > self.price)

    @property
    def options_summary(self):
        if not self.option_values or not isinstance(self.option_values, dict):
            return self.name
        pairs = [f"{k}: {v}" for k, v in self.option_values.items()]
        return ", ".join(pairs)

    @property
    def margin_pct(self):
        if self.price > 0 and self.cost_price > 0:
            margin = (self.price - self.cost_price) / self.price * 100
            return round(margin, 1)
        return 0.0

    def __str__(self):
        return f"{self.sku} · {self.name} (${self.price:.2f})"
