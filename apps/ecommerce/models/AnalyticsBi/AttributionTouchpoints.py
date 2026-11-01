from decimal import Decimal

from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class AttributionTouchpoint(TenantNumbered):
    NUMBER_PREFIX = "EATT"

    CHANNEL_CHOICES = [
        ("organic_search", "Organic Search"),
        ("paid_search", "Paid Search (SEM)"),
        ("paid_social", "Paid Social Ads"),
        ("email", "Email Marketing"),
        ("affiliate", "Affiliate / Partner"),
        ("direct", "Direct Storefront Traffic"),
        ("referral", "Referral Traffic"),
        ("influencer", "Influencer Campaign"),
        ("other", "Other"),
    ]

    ATTRIBUTION_MODEL_CHOICES = [
        ("first_touch", "First Touch (100% Acquisition)"),
        ("last_touch", "Last Touch (100% Conversion)"),
        ("linear", "Linear Multi-Touch"),
        ("time_decay", "Time Decay"),
    ]

    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attribution_touchpoints",
    )
    cart = models.ForeignKey(
        "ecommerce.Cart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attribution_touchpoints",
    )
    channel_type = models.CharField(
        max_length=32,
        choices=CHANNEL_CHOICES,
        default="direct",
    )
    attribution_model = models.CharField(
        max_length=20,
        choices=ATTRIBUTION_MODEL_CHOICES,
        default="last_touch",
    )
    campaign = models.ForeignKey(
        "ecommerce.MarketingCampaign",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attribution_touchpoints",
    )
    affiliate = models.ForeignKey(
        "ecommerce.AffiliatePartner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attribution_touchpoints",
    )
    utm_source = models.CharField(max_length=100, blank=True, default="")
    utm_medium = models.CharField(max_length=100, blank=True, default="")
    utm_campaign = models.CharField(max_length=100, blank=True, default="")
    touchpoint_timestamp = models.DateTimeField()
    attribution_weight = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("1.0000"),
    )
    attributed_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estimated_cac = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    landing_page_url = models.CharField(max_length=255, blank=True, default="")
    referrer_url = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "ecommerce_attribution_touchpoint"
        ordering = ["-touchpoint_timestamp"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_eatt_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "-touchpoint_timestamp"], name="idx_eatt_ten_time"),
            models.Index(fields=["tenant", "channel_type"], name="idx_eatt_ten_channel"),
            models.Index(fields=["tenant", "order"], name="idx_eatt_ten_order"),
            models.Index(fields=["tenant", "campaign"], name="idx_eatt_ten_camp"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_channel_type_display()} - ${self.attributed_revenue})"
