from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class PersonalizedExperience(TenantNumbered):
    NUMBER_PREFIX = "EPEX"

    EXPERIENCE_TYPE_CHOICES = [
        ("home_hero", "Homepage Hero Banner"),
        ("curated_collection", "Curated Category / Collection"),
        ("cart_abandonment", "Cart Abandonment Trigger"),
        ("browse_abandonment", "Browse Abandonment Trigger"),
        ("replenishment_reminder", "Replenishment Reorder Trigger"),
        ("win_back", "Win-Back Re-Engagement Trigger"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Campaign name, e.g. 'VIP Winter Hero', 'Cart Recovery 1hr'",
    )
    experience_type = models.CharField(
        max_length=30,
        choices=EXPERIENCE_TYPE_CHOICES,
        default="home_hero",
        help_text="Channel and format of personalized campaign",
    )
    target_segment = models.ForeignKey(
        "ecommerce.AudienceSegment",
        on_delete=models.CASCADE,
        related_name="experiences",
        help_text="Target audience cohort",
    )
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personalized_experiences",
        help_text="Target category for browse affinity or curated grid",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personalized_experiences",
        help_text="Featured product for hero banner or trigger payload",
    )
    headline = models.CharField(
        max_length=150,
        blank=True,
        help_text="Dynamic banner heading or email subject line",
    )
    subheadline = models.TextField(
        blank=True,
        help_text="Promotional body copy or value proposition",
    )
    cta_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Button text, e.g. 'Shop VIP Sale', 'Complete Your Order'",
    )
    cta_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Click-through destination URL",
    )
    hero_image_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Image or hero artwork asset URL",
    )
    trigger_delay_hours = models.PositiveIntegerField(
        default=1,
        help_text="Delay in hours before triggering lifecycle actions",
    )
    priority = models.PositiveIntegerField(
        default=10,
        help_text="Priority rank (higher number evaluated first)",
    )
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional campaign start schedule",
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional campaign end schedule",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active campaigns are evaluated in live storefront sessions",
    )
    impression_count = models.PositiveIntegerField(
        default=0,
        help_text="Total views or serves of this personalized experience",
    )
    click_count = models.PositiveIntegerField(
        default=0,
        help_text="Total clicks or interactions with this experience",
    )
    conversion_count = models.PositiveIntegerField(
        default=0,
        help_text="Attributed purchases or conversions",
    )

    class Meta:
        ordering = ["-priority", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_epex_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "experience_type", "priority"],
                name="idx_epex_ten_act_type_prio",
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "Campaign end date must be after the start date."})

    def __str__(self):
        return f"{self.name} ({self.get_experience_type_display()})"
