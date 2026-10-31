from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class VisualUgcMedia(TenantNumbered):
    NUMBER_PREFIX = "EUGC"

    MEDIA_TYPE_CHOICES = [
        ("photo", "Customer Photo"),
        ("video", "Customer Video"),
        ("instagram", "Instagram Post"),
        ("tiktok", "TikTok Video"),
    ]

    RIGHTS_STATUS_CHOICES = [
        ("approved", "Rights Approved / Uploaded"),
        ("pending_request", "Rights Requested"),
        ("rejected", "Rejected / No Rights"),
    ]

    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES, default="photo")
    media_url = models.URLField(max_length=500, help_text="Direct media URL")
    thumbnail_url = models.URLField(max_length=500, blank=True, help_text="Thumbnail preview URL")
    caption = models.TextField(blank=True, help_text="Customer caption or quote")
    uploader_name = models.CharField(max_length=120, blank=True)
    uploader_handle = models.CharField(max_length=80, blank=True, help_text="@social_handle")
    tagged_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="ugc_media",
        help_text="Product tagged in this visual asset",
    )
    tagged_variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ugc_media",
        help_text="Optional variant or SKU tagged in visual",
    )
    rights_status = models.CharField(max_length=25, choices=RIGHTS_STATUS_CHOICES, default="approved")
    is_shoppable = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=10)
    views_count = models.PositiveIntegerField(default=0)
    clicks_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_eugc_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "tagged_product", "is_published"], name="idx_eugc_ten_prod_pub"),
            models.Index(fields=["tenant", "rights_status"], name="idx_eugc_ten_rights"),
        ]

    def __str__(self):
        return f"{self.number} - {self.tagged_product.name} ({self.get_media_type_display()})"
