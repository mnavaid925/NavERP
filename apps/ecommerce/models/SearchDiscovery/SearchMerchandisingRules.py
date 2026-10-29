from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class SearchMerchandisingRule(TenantNumbered):
    NUMBER_PREFIX = "ESMR"

    RULE_TYPE_CHOICES = [
        ("query", "Search Query Trigger"),
        ("category", "Category Listing Trigger"),
        ("global", "Global Catalog Rule"),
    ]
    MATCH_TYPE_CHOICES = [
        ("exact", "Exact Query Match"),
        ("contains", "Contains Keyword"),
        ("starts_with", "Starts With Keyword"),
    ]
    ACTION_TYPE_CHOICES = [
        ("boost", "Boost Product Score"),
        ("bury", "Bury Product Score"),
        ("pin", "Pin Product to Slot"),
        ("block", "Block / Exclude Product"),
        ("redirect", "Query URL Redirect"),
        ("banner", "Promotional Banner Injection"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Rule description, e.g. 'Pin Air Max on Sneakers Query'",
    )
    rule_type = models.CharField(
        max_length=20,
        choices=RULE_TYPE_CHOICES,
        default="query",
    )
    trigger_query = models.CharField(
        max_length=200,
        blank=True,
        help_text="Target search query string when rule_type='query'",
    )
    match_type = models.CharField(
        max_length=20,
        choices=MATCH_TYPE_CHOICES,
        default="exact",
    )
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchandising_rules",
        help_text="Target category listing when rule_type='category'",
    )
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        default="boost",
    )
    boosted_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="merchandising_rules",
        help_text="Target product for boost, bury, pin, or block actions",
    )
    boost_weight = models.IntegerField(
        default=10,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
        help_text="Relevance score modifier (-100 to +100). Positive boosts; negative buries",
    )
    pin_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Fixed 1-indexed rank position (1=Slot 1, 2=Slot 2) when action_type='pin'",
    )
    redirect_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Target URL when action_type='redirect'",
    )
    banner_title = models.CharField(
        max_length=150,
        blank=True,
        help_text="Promotional banner heading when action_type='banner'",
    )
    banner_body = models.TextField(
        blank=True,
        help_text="Promotional banner body text / discount copy",
    )
    banner_image_url = models.URLField(
        blank=True,
        help_text="Promotional banner artwork or background image URL",
    )
    banner_link_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Click destination for banner",
    )
    priority = models.PositiveIntegerField(
        default=10,
        help_text="Evaluation priority (higher number evaluated first)",
    )
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional campaign start time",
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional campaign end time",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esmr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "rule_type"],
                name="idx_esmr_ten_act_type",
            ),
            models.Index(
                fields=["tenant", "trigger_query"],
                name="idx_esmr_ten_trig_q",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_action_type_display()})"

    def clean(self):
        super().clean()
        if self.rule_type == "query":
            if not self.trigger_query:
                raise ValidationError({"trigger_query": "Trigger search query is required for query rules."})
            self.trigger_query = self.trigger_query.strip().lower()
        elif self.rule_type == "category" and not self.target_category:
            raise ValidationError({"target_category": "Target category is required for category listing rules."})

        if self.action_type in ("boost", "bury", "pin", "block") and not self.boosted_product:
            raise ValidationError({"boosted_product": f"A target product is required for {self.get_action_type_display()}."})

        if self.action_type == "pin" and not self.pin_position:
            raise ValidationError({"pin_position": "Fixed slot position (1-50) is required for pinning rules."})

        if self.action_type == "redirect" and not self.redirect_url:
            raise ValidationError({"redirect_url": "Destination URL is required for query redirect rules."})

        for field_name, url_val in [("redirect_url", self.redirect_url), ("banner_link_url", self.banner_link_url)]:
            if url_val:
                url_clean = url_val.strip().lower()
                if url_clean.startswith(("javascript:", "data:", "vbscript:", "//")):
                    raise ValidationError({field_name: "Unsafe URL scheme or protocol-relative URL is not permitted."})
                if not (url_clean.startswith("/") or url_clean.startswith("http://") or url_clean.startswith("https://")):
                    raise ValidationError({field_name: "URL must be an absolute path (starting with /) or a full http:// or https:// URL."})

        if self.action_type == "banner" and not self.banner_title:
            raise ValidationError({"banner_title": "Banner title is required for promotional banner rules."})

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Campaign end date must be after the start date."})
