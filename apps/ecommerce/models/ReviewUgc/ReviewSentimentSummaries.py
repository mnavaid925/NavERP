from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class ReviewSentimentSummary(TenantNumbered):
    NUMBER_PREFIX = "ERVM"

    product = models.OneToOneField(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="review_summary",
        help_text="Catalog product being aggregated",
    )
    total_reviews = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
    rating_5_count = models.PositiveIntegerField(default=0)
    rating_4_count = models.PositiveIntegerField(default=0)
    rating_3_count = models.PositiveIntegerField(default=0)
    rating_2_count = models.PositiveIntegerField(default=0)
    rating_1_count = models.PositiveIntegerField(default=0)
    positive_sentiment_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    neutral_sentiment_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    negative_sentiment_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    top_positive_keywords = models.JSONField(
        default=list, blank=True, help_text="List of top praised attributes"
    )
    top_negative_keywords = models.JSONField(
        default=list, blank=True, help_text="List of top customer complaints"
    )
    improvement_recommendation = models.TextField(blank=True, help_text="Actionable quality guidance")
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-total_reviews", "-average_rating"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_ervm_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "average_rating"], name="idx_ervm_ten_avg_rate"),
            models.Index(fields=["tenant", "total_reviews"], name="idx_ervm_ten_tot_rev"),
        ]

    def __str__(self):
        return f"{self.number} - {self.product.name} ({self.average_rating}★ / {self.total_reviews} reviews)"

    def recalculate(self):
        """Aggregate ratings and sentiment metrics from approved customer reviews."""
        from apps.ecommerce.models.ReviewUgc.ProductReviews import ProductReview

        approved_reviews = ProductReview.objects.filter(
            tenant=self.tenant, product=self.product, status="approved"
        )
        total = approved_reviews.count()
        self.total_reviews = total

        if total > 0:
            r5 = approved_reviews.filter(rating=5).count()
            r4 = approved_reviews.filter(rating=4).count()
            r3 = approved_reviews.filter(rating=3).count()
            r2 = approved_reviews.filter(rating=2).count()
            r1 = approved_reviews.filter(rating=1).count()

            self.rating_5_count = r5
            self.rating_4_count = r4
            self.rating_3_count = r3
            self.rating_2_count = r2
            self.rating_1_count = r1

            sum_stars = (r5 * 5) + (r4 * 4) + (r3 * 3) + (r2 * 2) + (r1 * 1)
            self.average_rating = Decimal(str(round(sum_stars / total, 2)))

            pos = approved_reviews.filter(sentiment="positive").count()
            neu = approved_reviews.filter(sentiment="neutral").count()
            neg = approved_reviews.filter(sentiment="negative").count()

            self.positive_sentiment_pct = Decimal(str(round((pos / total) * 100, 2)))
            self.neutral_sentiment_pct = Decimal(str(round((neu / total) * 100, 2)))
            self.negative_sentiment_pct = Decimal(str(round((neg / total) * 100, 2)))
        else:
            self.average_rating = Decimal("0.00")
            self.rating_5_count = 0
            self.rating_4_count = 0
            self.rating_3_count = 0
            self.rating_2_count = 0
            self.rating_1_count = 0
            self.positive_sentiment_pct = Decimal("0.00")
            self.neutral_sentiment_pct = Decimal("0.00")
            self.negative_sentiment_pct = Decimal("0.00")

        self.save()

    def get_rating_pct(self, count):
        if self.total_reviews > 0:
            return round((count / self.total_reviews) * 100, 1)
        return 0.0

    @property
    def rating_5_pct(self):
        return self.get_rating_pct(self.rating_5_count)

    @property
    def rating_4_pct(self):
        return self.get_rating_pct(self.rating_4_count)

    @property
    def rating_3_pct(self):
        return self.get_rating_pct(self.rating_3_count)

    @property
    def rating_2_pct(self):
        return self.get_rating_pct(self.rating_2_count)

    @property
    def rating_1_pct(self):
        return self.get_rating_pct(self.rating_1_count)
