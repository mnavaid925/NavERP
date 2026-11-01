from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class BlogArticle(TenantNumbered):
    NUMBER_PREFIX = "EBLG"

    CATEGORY_CHOICES = [
        ("news", "Company News"),
        ("product_spotlight", "Product Spotlight"),
        ("guides_tutorials", "Guides & Tutorials"),
        ("lifestyle", "Lifestyle & Trends"),
        ("company_updates", "Announcements"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=255, help_text="Article title")
    slug = models.SlugField(max_length=255, help_text="URL slug")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_blog_articles",
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="guides_tutorials",
    )
    excerpt = models.TextField(max_length=500, help_text="Summary for cards and SEO")
    body_markdown = models.TextField(help_text="Detailed article markdown text")
    featured_media = models.ForeignKey(
        "ecommerce.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_articles",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated keyword tags",
    )
    reading_time_minutes = models.PositiveSmallIntegerField(
        default=3,
        help_text="Estimated read time in minutes",
    )
    allow_comments = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "ecommerce_blog_article"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_eblg_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="ecommerce_eblg_tenant_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "category"],
                name="idx_eblg_ten_stat_cat",
            ),
            models.Index(
                fields=["tenant", "is_featured"],
                name="idx_eblg_ten_feat",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:250]
        super().save(*args, **kwargs)
