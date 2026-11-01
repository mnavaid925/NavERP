from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class ContentBlock(TenantNumbered):
    prefix = "EBLK"

    BLOCK_TYPE_CHOICES = [
        ("hero_banner", "Hero Banner with CTA"),
        ("feature_grid", "3-Column Feature Grid"),
        ("product_carousel", "Catalog Product Carousel"),
        ("testimonial", "Customer Testimonial Slider"),
        ("cta_banner", "Call to Action Strip"),
        ("rich_text", "Formatted Editorial Text"),
        ("faq_accordion", "FAQ Accordion"),
        ("newsletter_signup", "Newsletter Signup Strip"),
    ]

    name = models.CharField(max_length=255, help_text="Internal block identifier")
    block_type = models.CharField(
        max_length=30,
        choices=BLOCK_TYPE_CHOICES,
        default="hero_banner",
    )
    headline = models.CharField(
        max_length=255,
        blank=True,
        help_text="Promotional heading",
    )
    subheadline = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secondary sub-title",
    )
    body_text = models.TextField(blank=True, help_text="Descriptive body content")
    media_asset = models.ForeignKey(
        "ecommerce.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_blocks",
    )
    cta_label = models.CharField(max_length=100, blank=True, help_text="Button text")
    cta_url = models.CharField(max_length=255, blank=True, help_text="Target button link")
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_blocks",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_blocks",
    )
    bg_color_class = models.CharField(
        max_length=50,
        default="bg-slate-50",
        help_text="Tailwind background class",
    )
    text_color_class = models.CharField(
        max_length=50,
        default="text-slate-900",
        help_text="Tailwind text class",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Display priority order",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "ecommerce_content_block"
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_eblk_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "block_type", "is_active"],
                name="idx_eblk_ten_type_act",
            ),
            models.Index(
                fields=["tenant", "sort_order"],
                name="idx_eblk_ten_order",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_block_type_display()})"
