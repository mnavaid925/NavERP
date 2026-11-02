from django.db import models
from django.utils import timezone
from apps.ecommerce.models._base import TenantNumbered


class MobileDeviceRegistration(TenantNumbered):
    NUMBER_PREFIX = "EMDR"

    PLATFORM_CHOICES = [
        ("ios", "Apple iOS"),
        ("android", "Google Android"),
        ("pwa_web", "PWA / Mobile Web Browser"),
    ]

    PUSH_PROVIDER_CHOICES = [
        ("apns", "Apple Push Notification Service (APNs)"),
        ("fcm", "Firebase Cloud Messaging (FCM)"),
        ("web_push", "W3C Web Push Protocol"),
        ("none", "No Push Configured"),
    ]

    LOCATION_PERMISSION_CHOICES = [
        ("always", "Always Allow in Background"),
        ("while_in_use", "Only While Using App"),
        ("denied", "Location Permission Denied"),
        ("not_determined", "Prompt Not Yet Triggered"),
    ]

    customer_profile = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mobile_devices",
        help_text="Registered customer account owner",
    )
    party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mobile_devices",
        help_text="Unified identity party record",
    )
    device_uuid = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Unique device installation UUID or hardware identifier",
    )
    device_platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default="ios",
    )
    device_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Hardware model (e.g. iPhone 15 Pro, Pixel 8)",
    )
    os_version = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="OS version string (e.g. iOS 17.4.1, Android 14)",
    )
    app_version = models.CharField(
        max_length=30,
        blank=True,
        default="1.0.0",
        help_text="Installed native shell or PWA build version",
    )
    push_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Device push notification registration token",
    )
    push_provider = models.CharField(
        max_length=20,
        choices=PUSH_PROVIDER_CHOICES,
        default="fcm",
    )
    push_enabled = models.BooleanField(
        default=True,
        help_text="Customer notification opt-in toggle",
    )
    biometric_enrolled = models.BooleanField(
        default=False,
        help_text="Device supports and user enrolled biometric authentication",
    )
    location_permission = models.CharField(
        max_length=20,
        choices=LOCATION_PERMISSION_CHOICES,
        default="not_determined",
    )
    badge_count = models.PositiveIntegerField(
        default=0,
        help_text="Current unread notification app badge count",
    )
    last_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Last reported device GPS latitude",
    )
    last_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Last reported device GPS longitude",
    )
    last_active_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last recorded telemetry or API ping timestamp",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active device capable of receiving messages",
    )

    class Meta:
        db_table = "ecommerce_mobile_device_registration"
        ordering = ["-last_active_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_emdr_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "device_uuid"],
                name="ecommerce_emdr_ten_uuid_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "device_platform"], name="idx_emdr_ten_plat"),
            models.Index(fields=["tenant", "customer_profile"], name="idx_emdr_ten_cust"),
            models.Index(fields=["tenant", "is_active"], name="idx_emdr_ten_act"),
            models.Index(fields=["tenant", "-last_active_at"], name="idx_emdr_ten_last_act"),
            models.Index(fields=["tenant", "is_active", "push_enabled"], name="idx_emdr_ten_push_act"),
        ]

    def __str__(self):
        platform_label = self.get_device_platform_display()
        model_str = f" - {self.device_model}" if self.device_model else ""
        return f"{self.number} ({platform_label}{model_str})"

    def record_activity(self, lat=None, lng=None):
        self.last_active_at = timezone.now()
        if lat is not None and lng is not None:
            self.last_latitude = lat
            self.last_longitude = lng
        self.save(update_fields=["last_active_at", "last_latitude", "last_longitude", "updated_at"])

    def reset_badge_count(self):
        self.badge_count = 0
        self.save(update_fields=["badge_count", "updated_at"])
