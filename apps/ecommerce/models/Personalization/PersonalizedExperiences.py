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

        # C2: Safe URL scheme validation
        if self.cta_url:
            lowered_cta = self.cta_url.strip().lower()
            if lowered_cta.startswith(("javascript:", "data:", "vbscript:")):
                raise ValidationError({"cta_url": "Dangerous URL scheme not allowed."})
            if not (lowered_cta.startswith(("/", "http://", "https://", "#"))):
                raise ValidationError({"cta_url": "URL must begin with '/', 'http://', 'https://', or '#'."})

        if self.hero_image_url:
            lowered_img = self.hero_image_url.strip().lower()
            if lowered_img.startswith(("javascript:", "data:", "vbscript:")):
                raise ValidationError({"hero_image_url": "Dangerous image URL scheme not allowed."})
            if not (lowered_img.startswith(("/", "http://", "https://"))):
                raise ValidationError({"hero_image_url": "Image URL must begin with '/', 'http://', or 'https://'."})

        # C3: Model-level tenant foreign key validation
        fk_errors = {}
        if self.target_segment_id and self.target_segment and self.target_segment.tenant_id != self.tenant_id:
            fk_errors["target_segment"] = "Target segment belongs to another workspace."
        if self.target_category_id and self.target_category and self.target_category.tenant_id != self.tenant_id:
            fk_errors["target_category"] = "Target category belongs to another workspace."
        if self.target_product_id and self.target_product and self.target_product.tenant_id != self.tenant_id:
            fk_errors["target_product"] = "Target product belongs to another workspace."
        if fk_errors:
            raise ValidationError(fk_errors)

    def __str__(self):
        return f"{self.name} ({self.get_experience_type_display()})"
