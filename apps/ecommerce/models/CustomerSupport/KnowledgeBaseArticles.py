from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class KnowledgeBaseArticle(TenantNumbered):
    NUMBER_PREFIX = "EKBA"

    CATEGORY_CHOICES = [
        ("shipping_delivery", "Shipping & Delivery"),
        ("returns_refunds", "Returns & Refunds"),
        ("ordering_payment", "Ordering & Payment"),
        ("product_sizing", "Product Specs & Sizing"),
        ("account_security", "Account & Security"),
        ("troubleshooting", "Troubleshooting & Care"),
        ("promotions", "Promotions & Loyalty"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    AUDIENCE_CHOICES = [
        ("all_visitors", "All Visitors"),
        ("registered_customers", "Registered Customers Only"),
        ("b2b_wholesale", "B2B Wholesale Accounts Only"),
    ]

    title = models.CharField(max_length=255, help_text="Article headline")
    slug = models.SlugField(max_length=255, help_text="SEO URL slug")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="shipping_delivery")
    summary = models.TextField(max_length=500, help_text="Brief summary snippet for search results")
    content = models.TextField(help_text="Full article / FAQ content")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    target_audience = models.CharField(max_length=25, choices=AUDIENCE_CHOICES, default="all_visitors")
    is_featured = models.BooleanField(default=False, help_text="Pin to top of knowledge base")
    view_count = models.PositiveIntegerField(default=0)
    helpful_votes = models.PositiveIntegerField(default=0)
    unhelpful_votes = models.PositiveIntegerField(default=0)
    keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for autocomplete")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_ecommerce_articles",
    )

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_ekba_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category", "status"], name="idx_ekba_ten_cat_stat"),
            models.Index(fields=["tenant", "is_featured", "status"], name="idx_ekba_ten_feat_stat"),
            models.Index(fields=["tenant", "slug"], name="idx_ekba_ten_slug"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(self.title)[:255]
        super().save(*args, **kwargs)

    @property
    def helpfulness_ratio(self):
        total = self.helpful_votes + self.unhelpful_votes
        if total == 0:
            return 100
        return int((self.helpful_votes / total) * 100)
