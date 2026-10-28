from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ProductRelationship(TenantNumbered):
    """Directed product merchandising relationships: cross-sells, up-sells, accessories, and bundles."""

    NUMBER_PREFIX = "PRL"

    RELATIONSHIP_CHOICES = [
        ("cross_sell", "Cross-Sell"),
        ("up_sell", "Up-Sell"),
        ("accessory", "Accessory"),
        ("bundle_kit", "Bundle / Kit Component"),
        ("bought_together", "Frequently Bought Together"),
    ]

    source_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="relationships_from",
        help_text="Primary product being viewed or purchased",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="relationships_to",
        help_text="Recommended, bundled, or related product",
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        default="cross_sell",
    )
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Bundle discount percentage when purchased with source product",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, help_text="Internal merchandising notes")

    class Meta:
        ordering = ["source_product__name", "sort_order", "target_product__name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_prl_tenant_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "source_product", "target_product", "relationship_type"],
                name="ecommerce_prl_src_tgt_type_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "source_product", "relationship_type"], name="ecom_prl_tnt_src_type_idx"),
        ]

    def clean(self):
        super().clean()
        if self.source_product_id and self.target_product_id:
            if self.source_product_id == self.target_product_id:
                raise ValidationError({"target_product": "A product cannot have a merchandising relationship with itself."})
            if self.source_product.tenant_id != self.tenant_id:
                raise ValidationError({"source_product": "Source product must belong to the current workspace."})
            if self.target_product.tenant_id != self.tenant_id:
                raise ValidationError({"target_product": "Target product must belong to the current workspace."})

    def __str__(self):
        return (
            f"{self.source_product.name} -> {self.target_product.name} "
            f"({self.get_relationship_type_display()})"
        )
