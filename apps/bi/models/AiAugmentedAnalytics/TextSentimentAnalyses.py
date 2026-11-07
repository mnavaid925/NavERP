from decimal import Decimal

from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class TextSentimentAnalysis(TenantNumbered):
    NUMBER_PREFIX = "BSNT"

    SOURCE_TYPE_CHOICES = [
        ("customer_review", "Customer Review / Rating"),
        ("support_ticket", "Customer Support Ticket"),
        ("survey_feedback", "Survey Feedback / NPS"),
        ("crm_note", "CRM Activity Note"),
        ("internal_comment", "Internal Team Comment"),
    ]

    SENTIMENT_CATEGORY_CHOICES = [
        ("very_positive", "Very Positive"),
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
        ("very_negative", "Very Negative"),
    ]

    source_type = models.CharField(max_length=24, choices=SOURCE_TYPE_CHOICES, default="customer_review")
    source_reference = models.CharField(max_length=120, help_text="Identifier of source record e.g. TKT-00421, REV-9811")
    text_content = models.TextField(help_text="Unstructured textual snippet analyzed")
    language = models.CharField(max_length=10, default="en")
    sentiment_category = models.CharField(max_length=20, choices=SENTIMENT_CATEGORY_CHOICES, default="neutral")
    polarity_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="Range from -1.00 (most negative) to +1.00 (most positive)")
    subjectivity_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.50"), help_text="Range from 0.00 (objective fact) to 1.00 (pure opinion)")
    thematic_tags = models.JSONField(default=list, blank=True, help_text="Extracted key themes e.g. ['billing', 'delivery_time', 'ease_of_use']")

    linked_party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="text_sentiment_records",
        help_text="Associated customer, vendor, or contact",
    )
    linked_org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="text_sentiment_records",
    )
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-analyzed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bsnt_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "source_type"], name="idx_bsnt_ten_src"),
            models.Index(fields=["tenant", "sentiment_category"], name="idx_bsnt_ten_cat"),
            models.Index(fields=["tenant", "analyzed_at"], name="idx_bsnt_ten_date"),
            models.Index(fields=["tenant", "linked_party"], name="idx_bsnt_ten_party"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_sentiment_category_display()} ({self.source_reference})"

    def get_absolute_url(self):
        return reverse("bi:text_sentiment_analysis_detail", kwargs={"pk": self.pk})

    @property
    def badge_color(self):
        if self.sentiment_category in ["very_positive", "positive"]:
            return "badge-green"
        if self.sentiment_category in ["very_negative", "negative"]:
            return "badge-red"
        return "badge-slate"
