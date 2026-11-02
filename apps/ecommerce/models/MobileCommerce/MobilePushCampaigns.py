from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.ecommerce.models._base import TenantNumbered


class MobilePushCampaign(TenantNumbered):
    NUMBER_PREFIX = "EMPC"

    CAMPAIGN_TYPE_CHOICES = [
        ("promotional", "Promotional Broadcast / Flash Sale"),
        ("transactional", "Transactional / Order Status Update"),
        ("abandoned_cart", "Abandoned Cart Recovery"),
        ("price_drop", "Wishlist Price Drop Alert"),
        ("back_in_stock", "Back in Stock Notification"),
        ("geofence_proximity", "Geofence Proximity Welcome"),
    ]

    TARGET_PLATFORM_CHOICES = [
        ("all", "All Platforms (iOS, Android, PWA)"),
        ("ios_only", "Apple iOS Devices Only"),
        ("android_only", "Google Android Devices Only"),
        ("pwa_only", "PWA Web Push Subscribers Only"),
    ]

    DEEP_LINK_TYPE_CHOICES = [
        ("home", "Storefront Home / Dashboard"),
        ("product", "Catalog Product Detail Page"),
        ("category", "Category Collection Page"),
        ("cart", "Shopping Cart / Checkout"),
        ("coupon", "Claim Coupon Promotion"),
        ("custom_url", "Custom In-App Deep Link / URL"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Editing)"),
        ("scheduled", "Scheduled for Broadcast"),
        ("sending", "Sending in Progress"),
        ("sent", "Sent / Completed"),
        ("cancelled", "Cancelled"),
    ]

    campaign_name = models.CharField(
        max_length=140,
        help_text="Internal operational campaign title",
    )
    campaign_type = models.CharField(
        max_length=30,
        choices=CAMPAIGN_TYPE_CHOICES,
        default="promotional",
    )
    target_platform = models.CharField(
        max_length=20,
        choices=TARGET_PLATFORM_CHOICES,
        default="all",
    )
    notification_title = models.CharField(
        max_length=100,
        help_text="Notification banner headline (max 100 chars)",
    )
    notification_body = models.TextField(
        help_text="Notification message body copy",
    )
    image_url = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional rich media banner image URL",
    )
    badge_increment = models.PositiveSmallIntegerField(
        default=1,
        help_text="Increment mobile app icon badge count by N",
    )
    sound_name = models.CharField(
        max_length=50,
        default="default",
        help_text="Audio chime file name (or default)",
    )
    deep_link_type = models.CharField(
        max_length=20,
        choices=DEEP_LINK_TYPE_CHOICES,
        default="home",
    )
    deep_link_url = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Specific deep link path or custom URL",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mobile_push_campaigns",
        help_text="Destination catalog product",
    )
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mobile_push_campaigns",
        help_text="Destination category collection",
    )
    target_coupon = models.ForeignKey(
        "ecommerce.CouponPromotion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mobile_push_campaigns",
        help_text="Attached promotional coupon",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled broadcast timestamp in UTC",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message dispatch began",
    )
    sent_count = models.PositiveIntegerField(
        default=0,
        help_text="Total push messages dispatched",
    )
    delivered_count = models.PositiveIntegerField(
        default=0,
        help_text="Total push receipts acknowledged",
    )
    opened_count = models.PositiveIntegerField(
        default=0,
        help_text="Total taps / opens recorded",
    )
    converted_count = models.PositiveIntegerField(
        default=0,
        help_text="Total orders converted from push taps",
    )
    converted_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total revenue attributed to campaign",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "ecommerce_mobile_push_campaign"
        ordering = ["-scheduled_for", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_empc_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_empc_ten_stat"),
            models.Index(fields=["tenant", "campaign_type"], name="idx_empc_ten_type"),
            models.Index(fields=["tenant", "scheduled_for"], name="idx_empc_ten_sched"),
        ]

    def __str__(self):
        return f"{self.campaign_name} ({self.number})"

    def calculate_open_rate_pct(self):
        if self.delivered_count and self.delivered_count > 0:
            return round((self.opened_count / self.delivered_count) * 100, 2)
        return 0.0

    def calculate_ctr_pct(self):
        if self.opened_count and self.opened_count > 0:
            return round((self.converted_count / self.opened_count) * 100, 2)
        return 0.0

    def dispatch_simulation(self, device_count=10):
        self.status = "sent"
        self.sent_at = timezone.now()
        self.sent_count = device_count
        self.delivered_count = max(0, device_count - 1)
        self.opened_count = max(0, int(device_count * 0.4))
        self.converted_count = max(0, int(device_count * 0.1))
        self.converted_revenue = Decimal(str(self.converted_count * 45))
        self.save()
