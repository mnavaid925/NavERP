from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class CustomerSatisfactionSurvey(TenantNumbered):
    NUMBER_PREFIX = "ECSF"

    SURVEY_TYPE_CHOICES = [
        ("ticket_csat", "Post-Ticket CSAT (1-5 Stars)"),
        ("order_delivery_csat", "Post-Delivery Order CSAT (1-5 Stars)"),
        ("storefront_nps", "Storefront NPS (0-10 Score)"),
    ]

    SENTIMENT_CHOICES = [
        ("positive", "Positive (Promoter / Satisfied)"),
        ("neutral", "Neutral (Passive)"),
        ("negative", "Negative (Detractor / Dissatisfied)"),
    ]

    FOLLOW_UP_CHOICES = [
        ("not_required", "No Follow-up Required"),
        ("pending_review", "Pending Supervisor Review"),
        ("contacted_customer", "Customer Contacted"),
        ("resolved_closed_loop", "Issue Resolved (Closed Loop)"),
    ]

    ticket = models.ForeignKey(
        "ecommerce.CustomerSupportTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="satisfaction_surveys",
        help_text="Support ticket evaluated",
    )
    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="satisfaction_surveys",
        help_text="Order evaluated for delivery/product experience",
    )
    customer = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="satisfaction_surveys",
        help_text="Customer profile anchor",
    )
    survey_type = models.CharField(max_length=25, choices=SURVEY_TYPE_CHOICES, default="ticket_csat")
    rating_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Score 1-5 for CSAT, 0-10 for NPS",
    )
    sentiment = models.CharField(max_length=15, choices=SENTIMENT_CHOICES, default="neutral")
    feedback_comment = models.TextField(blank=True, help_text="Shopper written comments")
    agent_rated = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rated_support_surveys",
        help_text="Support agent evaluated in this survey",
    )
    follow_up_status = models.CharField(max_length=25, choices=FOLLOW_UP_CHOICES, default="not_required")
    follow_up_notes = models.TextField(blank=True, help_text="Supervisor recovery and follow-up notes")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_support_surveys",
        help_text="Staff supervisor reviewing detractor feedback",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_ecsf_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "survey_type", "sentiment"], name="idx_ecsf_ten_type_snt"),
            models.Index(fields=["tenant", "follow_up_status"], name="idx_ecsf_ten_followup"),
            models.Index(fields=["tenant", "agent_rated"], name="idx_ecsf_ten_agent"),
            models.Index(fields=["tenant", "sentiment"], name="idx_ecsf_ten_sentiment"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_survey_type_display()} ({self.rating_score}/10)"

    def save(self, *args, **kwargs):
        # Auto-compute sentiment if not manually set or left as default neutral
        if not self.sentiment or self.sentiment == "neutral":
            if self.survey_type in ["ticket_csat", "order_delivery_csat"]:
                if self.rating_score >= 4:
                    self.sentiment = "positive"
                elif self.rating_score == 3:
                    self.sentiment = "neutral"
                else:
                    self.sentiment = "negative"
            elif self.survey_type == "storefront_nps":
                if self.rating_score >= 9:
                    self.sentiment = "positive"
                elif self.rating_score >= 7:
                    self.sentiment = "neutral"
                else:
                    self.sentiment = "negative"

        # Auto-flag negative feedback for closed-loop review
        if self.sentiment == "negative" and self.follow_up_status == "not_required":
            self.follow_up_status = "pending_review"

        super().save(*args, **kwargs)
