"""Sales 8.16 — MobileDeviceSession model."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

PLATFORM_CHOICES = [
    ("ios", "Apple iOS Native"),
    ("android", "Google Android Native"),
    ("web_pwa", "Progressive Web App (PWA)"),
]

SYNC_STATUS_CHOICES = [
    ("success", "Synchronized"),
    ("partial", "Partial Sync"),
    ("failed", "Sync Failed"),
    ("pending", "Pending Sync"),
]


class MobileDeviceSession(TenantNumbered):
    NUMBER_PREFIX = "MDS"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mobile_device_sessions",
    )
    device_uuid = models.CharField(max_length=64, db_index=True)
    device_name = models.CharField(max_length=120)
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default="web_pwa",
    )
    app_version = models.CharField(max_length=32, blank=True)
    push_token = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_trusted = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default="pending",
    )
    offline_records_cached = models.PositiveIntegerField(default=0)
    pending_uploads_count = models.PositiveIntegerField(default=0)
    last_ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_known_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_known_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_mds_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "user"], name="sales_mds_ten_usr_idx"),
            models.Index(fields=["tenant", "device_uuid"], name="sales_mds_ten_uuid_idx"),
            models.Index(fields=["tenant", "last_sync_status"], name="sales_mds_ten_stat_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.device_name} ({self.user.username})"

    def clean(self):
        super().clean()
        if self.user_id and self.tenant_id:
            user_tenant_id = getattr(self.user, "tenant_id", None)
            if user_tenant_id and user_tenant_id != self.tenant_id:
                raise ValidationError({"user": "Device owner belongs to another workspace."})

    def record_sync_event(self, status="success", cached_count=0, pending_count=0, ip=None):
        self.last_sync_at = timezone.now()
        self.last_sync_status = status
        self.offline_records_cached = cached_count
        self.pending_uploads_count = pending_count
        if ip:
            self.last_ip_address = ip
        self.save(update_fields=["last_sync_at", "last_sync_status", "offline_records_cached", "pending_uploads_count", "last_ip_address", "updated_at"])

    @property
    def is_outdated(self):
        if not self.last_sync_at:
            return True
        return timezone.now() - self.last_sync_at > timedelta(hours=24)
