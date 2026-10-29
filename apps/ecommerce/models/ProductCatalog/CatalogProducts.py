from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CatalogProduct(TenantNumbered):
    """Merchandised catalog product presentation header for eCommerce."""

    NUMBER_PREFIX = "EPRD"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    VISIBILITY_CHOICES = [
        ("storefront", "Storefront & Search"),
        ("hidden", "Hidden"),
        ("search_only", "Search Only"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_catalog_products",
        help_text="Canonical inventory master for single-SKU products or primary item anchor",
    )
    primary_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_products",
        help_text="Primary category for breadcrumbs and navigation",
    )
    categories = models.ManyToManyField(
        "ecommerce.StoreCategory",
        blank=True,
        related_name="products",
        help_text="Secondary category placements",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="storefront")
    brand = models.CharField(max_length=120, blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    hero_image_url = models.URLField(blank=True, help_text="Main product image URL")
    video_url = models.URLField(blank=True, help_text="Product video presentation URL")
    is_featured = models.BooleanField(default=False, help_text="Show in featured collections on homepage")
    is_digital = models.BooleanField(default=False, help_text="Digital product without physical shipping")
    pim_completeness = models.PositiveIntegerField(default=0, help_text="Calculated readiness score 0-100%")
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_prd_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="ecommerce_prd_tenant_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "visibility"], name="ecom_prd_tnt_stat_vis_idx"),
            models.Index(fields=["tenant", "brand"], name="ecom_prd_tnt_brand_idx"),
            models.Index(fields=["tenant", "-created_at"], name="ecom_prd_tnt_created_idx"),
        ]

    def clean(self):
        super().clean()
        if self.primary_category_id and self.primary_category.tenant_id != self.tenant_id:
            raise ValidationError({"primary_category": "Primary category must belong to the same workspace."})
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "Linked inventory item must belong to the same workspace."})

    def calculate_pim_completeness(self):
        score = 0
        if self.name:
            score += 15
        if self.slug:
            score += 10
        if self.short_description:
            score += 15
        if self.description:
            score += 15
        if self.primary_category_id:
            score += 15
        if self.hero_image_url:
            score += 15
        if self.brand:
            score += 15
        return min(score, 100)

    def save(self, *args, **kwargs):
        self.pim_completeness = self.calculate_pim_completeness()
        if self.status == "active" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def sku(self):
        if self.item_id and getattr(self.item, "sku", None):
            return self.item.sku
        first_var = self.variants.first()
        if first_var and first_var.sku:
            return first_var.sku
        return self.number

    @property
    def base_price(self):
        first_var = self.variants.first()
        if first_var and first_var.price is not None:
            return f"{first_var.price:.2f}"
        return "0.00"

    @property
    def category(self):
        return self.primary_category

    @property
    def price_range_display(self):
        active_vars = [v for v in self.variants.all() if v.is_active]
        if not active_vars:
            return "No price set"
        prices = [v.price for v in active_vars if v.price is not None]
        if not prices:
            return "No price set"
        min_p = min(prices)
        max_p = max(prices)
        if min_p == max_p:
            return f"${min_p:.2f}"
        return f"${min_p:.2f} - ${max_p:.2f}"

    @property
    def total_variants_count(self):
        return len(self.variants.all())

    def __str__(self):
        return f"{self.name} ({self.number})"
