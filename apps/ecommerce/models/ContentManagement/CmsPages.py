from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CmsPage(TenantNumbered):
    """Dynamic store page and promotional landing page engine with SEO and A/B test tracking."""

    NUMBER_PREFIX = "EPAG"

    PAGE_TYPE_CHOICES = [
        ("standard", "Standard Store Page"),
        ("landing", "Promotional Landing Page"),
        ("policy", "Store Policy / Legal"),
        ("about", "About Us / Story"),
        ("contact", "Contact Us"),
        ("homepage", "Custom Homepage Layout"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    LAYOUT_CHOICES = [
        ("full_width", "Full Width (No Sidebars)"),
        ("boxed", "Boxed Container"),
        ("sidebar_left", "Left Sidebar"),
        ("sidebar_right", "Right Sidebar"),
        ("minimal_landing", "Minimal Landing (No Header/Footer)"),
    ]

    title = models.CharField(max_length=255, help_text="Public page headline")
    slug = models.SlugField(max_length=255, help_text="URL path slug")
    page_type = models.CharField(max_length=25, choices=PAGE_TYPE_CHOICES, default="standard")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    template_layout = models.CharField(max_length=25, choices=LAYOUT_CHOICES, default="full_width")

    meta_title = models.CharField(max_length=255, blank=True, help_text="SEO title tag")
    meta_description = models.TextField(max_length=500, blank=True, help_text="SEO meta description snippet")
    canonical_url = models.URLField(max_length=500, blank=True, help_text="Canonical URL override")
    is_indexable = models.BooleanField(default=True, help_text="Allow search engines to index")

    content_json = models.JSONField(default=dict, blank=True, help_text="Structured layout blocks payload")
    raw_html_body = models.TextField(blank=True, help_text="Editorial or fallback HTML content")

    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)

    is_ab_test_active = models.BooleanField(default=False)
    ab_variant_label = models.CharField(max_length=50, blank=True, help_text="A/B variant name e.g. Variant B")
    ab_traffic_percentage = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Target traffic split percentage (0-100)",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_epag_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="ecommerce_epag_tenant_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "page_type"], name="idx_epag_ten_stat_type"),
            models.Index(fields=["tenant", "is_ab_test_active"], name="idx_epag_ten_ab"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_page_type_display()})"

    def save(self, *args, **kwargs):
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
