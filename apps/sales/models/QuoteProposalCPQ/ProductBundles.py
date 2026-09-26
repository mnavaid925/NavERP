"""ProductBundleOption model for CPQ product bundling and compatibility rules."""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.sales.models._base import TenantNumbered


class ProductBundleOption(TenantNumbered):
    """Configuration rule linking a parent bundle product to component products and physical SKUs."""

    NUMBER_PREFIX = "BND"

    COMPATIBILITY_CHOICES = [
        ("none", "None"),
        ("requires", "Requires"),
        ("excludes", "Mutually Exclusive With"),
        ("recommends", "Recommended With"),
    ]

    name = models.CharField(max_length=255)
    bundle_product = models.ForeignKey(
        "crm.Product",
        on_delete=models.CASCADE,
        related_name="bundle_options",
        help_text="Parent bundle product header",
    )
    component_product = models.ForeignKey(
        "crm.Product",
        on_delete=models.CASCADE,
        related_name="component_in_bundles",
        help_text="Component option product item",
    )
    component_item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="component_in_bundles",
        help_text="Physical inventory SKU for stock reservation & ERP fulfillment",
    )
    option_group = models.CharField(
        max_length=50,
        default="Components",
        help_text="e.g., Hardware, Software, Support, Accessories, Warranty",
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Must be selected when the parent bundle is added to a quote",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Pre-selected by default during guided selling / configuration",
    )
    min_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    max_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("10"),
        validators=[MinValueValidator(0)],
    )
    default_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    unit_price_override = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Special bundle unit price (overrides product list price if set)",
    )
    discount_pct_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Bundled discount percentage override",
    )
    compatibility_rule = models.CharField(
        max_length=20,
        choices=COMPATIBILITY_CHOICES,
        default="none",
        help_text="Validation rule governing dependency on other products",
    )
    depends_on_product = models.ForeignKey(
        "crm.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependent_bundle_options",
        help_text="Product required or mutually excluded by this option",
    )
    sort_order = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["bundle_product", "option_group", "sort_order", "name"]
        indexes = [
            models.Index(fields=["tenant", "bundle_product", "is_active"], name="sales_bnd_bundle_act_idx"),
            models.Index(fields=["tenant", "component_product"], name="sales_bnd_comp_prod_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.bundle_product.name} → {self.component_product.name} ({self.option_group})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.bundle_product_id and self.component_product_id and self.bundle_product_id == self.component_product_id:
            raise ValidationError("A product cannot be a component of itself in a bundle.")
        if self.min_quantity > self.max_quantity:
            raise ValidationError("Minimum quantity cannot exceed maximum quantity.")
        if self.default_quantity < self.min_quantity or self.default_quantity > self.max_quantity:
            raise ValidationError("Default quantity must be within the min and max quantity bounds.")
