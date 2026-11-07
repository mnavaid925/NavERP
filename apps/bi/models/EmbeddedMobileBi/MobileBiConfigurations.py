from django.conf import settings
from django.db import models

from apps.bi.models._base import TenantNumbered


class MobileBiConfiguration(TenantNumbered):
    NUMBER_PREFIX = "MOB"

    TOUCH_PRESET_CHOICES = [
        ("compact", "Compact Grid (High Density)"),
        ("comfortable", "Comfortable Cards (Standard Touch)"),
        ("large_cards", "Large Cards (Single Column / Accessible)"),
    ]

    DIGEST_FREQUENCY_CHOICES = [
        ("realtime", "Instant Push on Alert Trigger"),
        ("hourly", "Hourly Push Digest"),
        ("daily_morning", "Daily Morning Briefing (08:00)"),
        ("weekly", "Weekly Executive Digest (Monday 08:00)"),
        ("disabled", "Push Insights Disabled"),
    ]

    STATUS_CHOICES = [
        ("active", "Active Profile"),
        ("inactive", "Inactive Profile"),
    ]

    name = models.CharField(max_length=200)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_mobile_configs",
        help_text="Optional user-specific profile; leave empty for role/team default",
    )
    is_default_profile = models.BooleanField(
        default=False,
        help_text="Default mobile configuration for all users in tenant",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    offline_caching_enabled = models.BooleanField(
        default=True,
        help_text="Allow Service Worker to cache analytical snapshots locally on device",
    )
    cache_max_age_hours = models.PositiveIntegerField(
        default=24,
        help_text="Maximum age before offline cached snapshot is considered stale",
    )
    max_cache_storage_mb = models.PositiveIntegerField(
        default=100,
        help_text="Maximum storage quota allowed for offline analytics data (MB)",
    )
    sync_on_wifi_only = models.BooleanField(
        default=False,
        help_text="Restrict automatic background snapshot downloads to Wi-Fi connections",
    )

    pinned_dashboard_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of BiDashboard IDs pre-fetched for offline access",
    )
    pinned_report_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of ReportDefinition IDs pre-fetched for offline access",
    )

    touch_layout_preset = models.CharField(
        max_length=24,
        choices=TOUCH_PRESET_CHOICES,
        default="comfortable",
    )
    enable_push_insights = models.BooleanField(
        default=True,
        help_text="Send proactive KPI threshold alerts and daily summaries to mobile client",
    )
    push_digest_frequency = models.CharField(
        max_length=24,
        choices=DIGEST_FREQUENCY_CHOICES,
        default="daily_morning",
    )

    require_biometric_lock = models.BooleanField(
        default=False,
        help_text="Enforce FaceID / Fingerprint / PIN authentication after inactivity timeout",
    )
    inactivity_lock_minutes = models.PositiveIntegerField(
        default=5,
        help_text="Inactivity duration before locking mobile offline analytics view",
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Most recent mobile client synchronization timestamp",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_created_mobile_configs",
    )

    class Meta:
        db_table = "bi_mobile_configuration"
        ordering = ["-is_default_profile", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_mob_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_mob_ten_stat"),
            models.Index(fields=["tenant", "target_user"], name="idx_mob_ten_usr"),
            models.Index(fields=["tenant", "is_default_profile"], name="idx_mob_ten_default"),
            models.Index(fields=["tenant", "created_at"], name="idx_mob_ten_created"),
        ]

    def __str__(self):
        user_label = f" ({self.target_user.username})" if self.target_user else " (Tenant Default)" if self.is_default_profile else ""
        return f"{self.number} - {self.name}{user_label}"
