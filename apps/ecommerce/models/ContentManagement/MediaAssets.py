from django.conf import settings
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class MediaAsset(TenantNumbered):
    prefix = "EMED"

    MEDIA_TYPE_CHOICES = [
        ("image", "Image / Graphic"),
        ("video", "Video Embed / Clip"),
        ("document", "PDF Document"),
        ("banner", "Promotional Banner"),
        ("icon", "SVG / Icon"),
    ]

    FOLDER_CHOICES = [
        ("banners", "Store Banners"),
        ("blog", "Blog Imagery"),
        ("pages", "Page Assets"),
        ("marketing", "Marketing Collateral"),
        ("icons", "UI Icons"),
        ("uncategorized", "Uncategorized"),
    ]

    title = models.CharField(max_length=255, help_text="Media asset display name")
    file_url = models.URLField(max_length=500, help_text="Direct HTTPS asset URL")
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Accessibility & SEO alt text",
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional asset caption",
    )
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default="image",
    )
    folder_category = models.CharField(
        max_length=30,
        choices=FOLDER_CHOICES,
        default="uncategorized",
    )
    file_size_bytes = models.PositiveIntegerField(
        default=0,
        help_text="File size in bytes",
    )
    mime_type = models.CharField(max_length=100, default="image/jpeg")
    width_px = models.PositiveIntegerField(null=True, blank=True)
    height_px = models.PositiveIntegerField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_ecommerce_media",
    )

    class Meta:
        db_table = "ecommerce_media_asset"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_emed_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "media_type", "folder_category"],
                name="idx_emed_ten_type_cat",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"
