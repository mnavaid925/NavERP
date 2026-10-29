from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class RecommendationStrategy(TenantNumbered):
    NUMBER_PREFIX = "EREC"

    ALGORITHM_CHOICES = [
        ("related_products", "Related Products (Content-Based)"),
        ("frequently_bought_together", "Frequently Bought Together (Co-occurrence)"),
        ("collaborative_filtering", "Shoppers Also Viewed / Bought"),
        ("trending_popular", "Trending & Popular Items"),
        ("recently_viewed", "Recently Viewed (Shopper History)"),
        ("replenishment", "Repurchase & Replenishment Reminder"),
        ("hybrid", "Hybrid Multi-Factor Score"),
    ]

    PLACEMENT_CHOICES = [
        ("pdp_related", "Product Detail Page (PDP)"),
        ("cart_cross_sell", "Cart Drawer / Cross-Sell"),
        ("homepage_feed", "Homepage Recommendation Feed"),
        ("category_trending", "Category Top Sellers / Trending"),
        ("checkout_upsell", "Checkout Order Bump"),
        ("email_block", "Email / Notification Block"),
    ]

    FALLBACK_CHOICES = [
        ("trending_popular", "Site Trending & Best Sellers"),
        ("category_top", "Category Top Sellers"),
        ("new_arrivals", "New Arrivals"),
        ("none", "No Fallback (Hide Widget)"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Strategy name, e.g. 'PDP Similar Styles', 'Cart Cross-Sell'",
    )
    code = models.CharField(
        max_length=60,
        help_text="Machine code identifier, e.g. 'pdp-similar', 'cart-upsell'",
    )
    algorithm = models.CharField(
        max_length=30,
        choices=ALGORITHM_CHOICES,
        default="related_products",
        help_text="Core recommendation algorithm logic",
    )
    placement = models.CharField(
        max_length=30,
        choices=PLACEMENT_CHOICES,
        default="pdp_related",
        help_text="Storefront placement slot",
    )
    fallback_strategy = models.CharField(
        max_length=30,
        choices=FALLBACK_CHOICES,
        default="trending_popular",
        help_text="Fallback behavior when primary algorithm yields sparse results",
    )
    max_items = models.PositiveIntegerField(
        default=6,
        help_text="Max items returned in recommendation payload",
    )
    min_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Minimum average star rating required",
    )
    same_brand_only = models.BooleanField(
        default=False,
        help_text="Restrict results to the same brand as target item",
    )
    only_in_stock = models.BooleanField(
        default=True,
        help_text="Only recommend in-stock items",
    )
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_strategies",
        help_text="Category constraint",
    )
    target_segment = models.ForeignKey(
        "ecommerce.AudienceSegment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_strategies",
        help_text="Optional shopper segment restriction",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active strategies are served by the recommendation engine",
    )
    description = models.TextField(
        blank=True,
        help_text="Internal notes on business logic and merchandising intent",
    )

    class Meta:
        ordering = ["placement", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_erec_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="ecommerce_erec_code_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "placement"],
                name="idx_erec_ten_act_place",
            ),
        ]

    def clean(self):
        super().clean()
        if self.code:
            self.code = slugify(self.code)
        if self.name and not self.code:
            self.code = slugify(self.name)
        if self.max_items < 1 or self.max_items > 50:
            raise ValidationError({"max_items": "Max items must be between 1 and 50."})
        if self.min_rating < Decimal("0.00") or self.min_rating > Decimal("5.00"):
            raise ValidationError({"min_rating": "Min rating must be between 0.00 and 5.00."})

    def __str__(self):
        return f"{self.name} ({self.get_algorithm_display()})"
