from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class ProductReview(TenantNumbered):
    NUMBER_PREFIX = "EPRV"

    RATING_CHOICES = [
        (1, "1 Star - Poor"),
        (2, "2 Stars - Fair"),
        (3, "3 Stars - Good"),
        (4, "4 Stars - Very Good"),
        (5, "5 Stars - Excellent"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Moderation"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("flagged_spam", "Flagged as Spam"),
    ]

    SENTIMENT_CHOICES = [
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
        ("mixed", "Mixed"),
    ]

    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="customer_reviews",
        help_text="Product being reviewed",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_reviews",
        help_text="Specific variant or SKU reviewed",
    )
    customer = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        help_text="Customer profile anchor",
    )
    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        help_text="Order reference for verified purchase verification",
    )
    reviewer_name = models.CharField(max_length=120, help_text="Public display name")
    reviewer_email = models.EmailField(help_text="Private email for verification")
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    title = models.CharField(max_length=200, help_text="Review headline")
    body = models.TextField(help_text="Detailed customer review text")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="pending")
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default="neutral")
    sentiment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Polarity score from -1.00 (negative) to +1.00 (positive)",
    )
    is_verified_purchase = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False, help_text="Pin to top of review list")
    media_urls = models.JSONField(default=list, blank=True, help_text="List of attached photo/video URLs")
    helpful_votes = models.PositiveIntegerField(default=0)
    unhelpful_votes = models.PositiveIntegerField(default=0)
    merchant_response = models.TextField(blank=True, help_text="Official merchant public reply")
    merchant_response_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews",
    )
    moderation_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_eprv_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_eprv_ten_stat"),
            models.Index(fields=["tenant", "product", "status"], name="idx_eprv_ten_prod_stat"),
            models.Index(fields=["tenant", "rating", "status"], name="idx_eprv_ten_rate_stat"),
            models.Index(fields=["tenant", "sentiment"], name="idx_eprv_ten_snt"),
        ]

    def __str__(self):
        return f"{self.number} - {self.product.name} ({self.rating}★)"

    @property
    def star_range(self):
        return range(self.rating)

    @property
    def empty_star_range(self):
        return range(max(0, 5 - self.rating))
