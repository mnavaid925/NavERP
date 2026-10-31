from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class SeoMetadataRule(TenantNumbered):
    NUMBER_PREFIX = "ESEO"

    RULE_TYPE_CHOICES = [
        ("global_default", "Global Storefront Default"),
        ("category_template", "Category Level Dynamic Template"),
        ("product_template", "Product Level Dynamic Template"),
        ("custom_url", "Custom URL Specific Override"),
    ]

    SCHEMA_TYPE_CHOICES = [
        ("Product", "Product (Schema.org)"),
        ("BreadcrumbList", "BreadcrumbList (Schema.org)"),
        ("Organization", "Organization (Schema.org)"),
        ("WebSite", "WebSite (Schema.org)"),
        ("FAQPage", "FAQPage (Schema.org)"),
        ("None", "None / Disabled"),
    ]

    ROBOTS_CHOICES = [
        ("index_follow", "index, follow"),
        ("noindex_follow", "noindex, follow"),
        ("noindex_nofollow", "noindex, nofollow"),
        ("index_nofollow", "index, nofollow"),
    ]

    CHANGEFREQ_CHOICES = [
        ("always", "always"),
        ("hourly", "hourly"),
        ("daily", "daily"),
        ("weekly", "weekly"),
        ("monthly", "monthly"),
        ("yearly", "yearly"),
        ("never", "never"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Administrative label, e.g. 'Footwear Category Dynamic Meta Rule'",
    )
    rule_type = models.CharField(
        max_length=25,
        choices=RULE_TYPE_CHOICES,
        default="product_template",
        help_text="Application scope for dynamic meta generation",
    )
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seo_rules",
        help_text="Target category scope for category rules",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seo_rules",
        help_text="Specific product override for custom product rules",
    )
    url_path_pattern = models.CharField(
        max_length=255,
        blank=True,
        help_text="URL pattern for custom pages, e.g. '/promotions/summer-sale/'",
    )
    meta_title_template = models.CharField(
        max_length=200,
        help_text="SEO Title template supporting tokens: {product_name}, {brand}, {category}, {price}, {site_name}",
    )
    meta_description_template = models.TextField(
        help_text="Meta Description template supporting dynamic variable tokens",
    )
    json_ld_schema_type = models.CharField(
        max_length=30,
        choices=SCHEMA_TYPE_CHOICES,
        default="Product",
        help_text="Primary Schema.org structured data archetype",
    )
    canonical_url_override = models.URLField(
        blank=True,
        help_text="Custom canonical URL if different from request URL",
    )
    og_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="OpenGraph title for social media sharing cards",
    )
    og_description = models.TextField(
        blank=True,
        help_text="OpenGraph description snippet for social sharing",
    )
    og_image_url = models.URLField(
        blank=True,
        help_text="Social preview image link",
    )
    robots_directive = models.CharField(
        max_length=30,
        choices=ROBOTS_CHOICES,
        default="index_follow",
        help_text="Robots meta tag indexation directive",
    )
    sitemap_included = models.BooleanField(
        default=True,
        help_text="Include matching pages in dynamic XML sitemap generation",
    )
    sitemap_priority = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.80"),
        help_text="Sitemap crawl priority from 0.00 to 1.00",
    )
    sitemap_changefreq = models.CharField(
        max_length=15,
        choices=CHANGEFREQ_CHOICES,
        default="weekly",
        help_text="Sitemap update frequency hint for web crawlers",
    )
    target_keyword = models.CharField(
        max_length=100,
        blank=True,
        help_text="Primary focus keyword for organic rank monitoring",
    )
    tracked_rank_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Monitored search engine SERP rank position",
    )
    rank_tracked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of latest SERP rank check",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable or disable this rule globally",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_eseo_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "rule_type"],
                name="idx_eseo_ten_act_type",
            ),
            models.Index(
                fields=["tenant", "target_keyword"],
                name="idx_eseo_ten_keyword",
            ),
        ]

    def __str__(self):
        return f"{self.name} [{self.get_rule_type_display()}]"

    def render_title(self, context=None):
        if not context:
            return self.meta_title_template
        rendered = self.meta_title_template
        for k, v in context.items():
            rendered = rendered.replace(f"{{{k}}}", str(v))
        return rendered

    def render_description(self, context=None):
        if not context:
            return self.meta_description_template
        rendered = self.meta_description_template
        for k, v in context.items():
            rendered = rendered.replace(f"{{{k}}}", str(v))
        return rendered
