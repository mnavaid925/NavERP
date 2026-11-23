import json

from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentSearchAlert(TenantNumbered):
    NUMBER_PREFIX = "DALT"

    FREQUENCY_CHOICES = (
        ("realtime", "Immediate / Real-time"),
        ("daily", "Daily Digest"),
        ("weekly", "Weekly Digest"),
        ("monthly", "Monthly Digest"),
    )

    DELIVERY_CHOICES = (
        ("in_app", "In-App Notification"),
        ("email", "Email Notification"),
        ("both", "In-App & Email"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("paused", "Paused"),
        ("failed", "Delivery Failed"),
    )

    FREQUENCY_CSS = {
        "realtime": "badge-green",
        "daily": "badge-info",
        "weekly": "badge-amber",
        "monthly": "badge-slate",
    }

    STATUS_CSS = {
        "active": "badge-green",
        "paused": "badge-amber",
        "failed": "badge-red",
    }

    DELIVERY_CSS = {
        "in_app": "badge-info",
        "email": "badge-green",
        "both": "badge-amber",
    }

    saved_search = models.ForeignKey(
        "documents.DocumentSavedSearch",
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_search_alerts",
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="daily",
        db_index=True,
    )
    delivery_channel = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default="in_app",
    )
    last_notified_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    new_matches_count = models.PositiveIntegerField(default=0)
    last_result_ids = models.TextField(blank=True, default="[]")
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Search Alert"
        verbose_name_plural = "Search Alerts"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_dalt_ten_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "saved_search", "subscriber"],
                name="doc_dalt_tnt_svd_sub_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "frequency", "status"],
                name="doc_dalt_tnt_frq_stat_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.saved_search.name} ({self.subscriber.username})"

    @property
    def frequency_badge_class(self):
        return self.FREQUENCY_CSS.get(self.frequency, "badge-slate")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def delivery_badge_class(self):
        return self.DELIVERY_CSS.get(self.delivery_channel, "badge-info")

    def get_last_result_ids_list(self):
        if not self.last_result_ids:
            return []
        try:
            return json.loads(self.last_result_ids)
        except (ValueError, TypeError):
            return []
