from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class StorefrontCatalogAssignment(TenantNumbered):
    NUMBER_PREFIX = "ESCA"

    PUBLISH_STATUS_CHOICES = [
        ("published", "Published / Live"),
        ("hidden", "Hidden from Catalog"),
        ("coming_soon", "Coming Soon"),
        ("discontinued", "Discontinued in this Store"),
    ]

    storefront = models.ForeignKey(
        "ecommerce.StorefrontInstance",
        on_delete=models.CASCADE,
        related_name="catalog_assignments",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="storefront_assignments",
    )
    is_visible = models.BooleanField(default=True, help_text="Controls if product appears in storefront catalog")
    is_featured = models.BooleanField(default=False, help_text="Highlight on storefront homepage and featured carousels")
    custom_title = models.CharField(max_length=255, blank=True, help_text="Storefront-specific product title override")
    custom_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Storefront-specific retail price override",
    )
    custom_currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storefront_custom_prices",
    )
    storefront_badge = models.CharField(max_length=50, blank=True, help_text="Custom badge text, e.g. 'Online Exclusive'")
    sort_order = models.IntegerField(default=0)
    publish_status = models.CharField(max_length=20, choices=PUBLISH_STATUS_CHOICES, default="published")

    class Meta:
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_esca_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "storefront", "product"], name="ecommerce_esca_store_prod_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "storefront", "publish_status"], name="idx_esca_ten_store_pub"),
            models.Index(fields=["tenant", "is_featured"], name="idx_esca_ten_feat"),
            models.Index(fields=["tenant", "publish_status"], name="idx_esca_ten_pubstat"),
        ]

    def __str__(self):
        title = self.custom_title or self.number
        return f"{title} ({self.number})"
