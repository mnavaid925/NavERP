import secrets

from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered, TenantOwned


class CustomerWishlist(TenantNumbered):
    NUMBER_PREFIX = "EWSL"

    VISIBILITY_CHOICES = [
        ("private", "Private (Only Me)"),
        ("shared", "Shared (Link Access)"),
        ("public", "Public (Searchable)"),
    ]

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="ecommerce_wishlists",
    )
    name = models.CharField(max_length=120, default="My Wishlist")
    slug = models.SlugField(max_length=140, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default="private",
    )
    is_default = models.BooleanField(default=True)
    share_token = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "customer"], name="idx_ewsl_ten_cust"),
            models.Index(fields=["tenant", "share_token"], name="idx_ewsl_ten_token"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.customer})"

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(32)[:64]
        if not self.slug:
            self.slug = slugify(self.name)[:140]

        if self.is_default and self.tenant_id and self.customer_id:
            CustomerWishlist.objects.filter(
                tenant=self.tenant,
                customer=self.customer,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)


class CustomerWishlistItem(TenantOwned):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("highest", "Must Have"),
    ]

    wishlist = models.ForeignKey(
        CustomerWishlist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wishlist_items",
    )
    desired_quantity = models.PositiveIntegerField(default=1)
    priority = models.CharField(
        max_length=15,
        choices=PRIORITY_CHOICES,
        default="medium",
    )
    comment = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "wishlist"], name="idx_ewsi_ten_wish"),
            models.Index(fields=["tenant", "product"], name="idx_ewsi_ten_prod"),
        ]

    def __str__(self):
        return f"{self.wishlist.name} - {self.product.name} (x{self.desired_quantity})"
