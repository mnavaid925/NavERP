import secrets

from django.conf import settings
from django.db import models

from apps.bi.models._base import TenantNumbered


class BiWebhookSubscription(TenantNumbered):
    NUMBER_PREFIX = "BWHK"

    PAYLOAD_FORMAT_CHOICES = [
        ("standard_json", "NavERP Standard Analytical JSON"),
        ("cloudevents_v1", "CloudEvents v1.0 Standard"),
        ("slack_compatible", "Slack Block Kit Compatible"),
        ("compact_minimal", "Compact Minimalist Payload"),
    ]

    STATUS_CHOICES = [
        ("active", "Active (Receiving Events)"),
        ("suspended", "Suspended (Excessive Consecutive Failures)"),
        ("failing", "Degraded (Intermittent 5xx Errors)"),
        ("disabled", "Disabled by Administrator"),
    ]

    name = models.CharField(max_length=200)
    endpoint_url = models.URLField(
        max_length=500,
        help_text="Target destination HTTPS URL for signed webhook deliveries",
    )
    secret_token = models.CharField(
        max_length=128,
        blank=True,
        help_text="Secret key used to compute the X-NavERP-Signature HMAC-SHA256 digest",
    )

    event_types = models.JSONField(
        default=list,
        blank=True,
        help_text="List of subscribed event strings (e.g. kpi.breached, report.ready, anomaly.detected)",
    )
    payload_format = models.CharField(
        max_length=30,
        choices=PAYLOAD_FORMAT_CHOICES,
        default="standard_json",
    )
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom HTTP request headers (e.g. Authorization, X-Environment)",
    )

    max_retries = models.PositiveIntegerField(
        default=3,
        help_text="Maximum retry attempts on 5xx status codes or network timeouts",
    )
    timeout_seconds = models.PositiveIntegerField(
        default=10,
        help_text="Socket timeout threshold in seconds",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="active",
    )
    consecutive_failures = models.PositiveIntegerField(default=0)

    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_response_code = models.PositiveIntegerField(null=True, blank=True)
    last_response_time_ms = models.PositiveIntegerField(default=0)
    last_error_log = models.TextField(blank=True)
    total_deliveries = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_created_webhooks",
    )

    class Meta:
        db_table = "bi_webhook_subscription"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bwhk_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bwhk_ten_stat"),
            models.Index(fields=["tenant", "is_active"], name="idx_bwhk_ten_act"),
            models.Index(fields=["tenant", "payload_format"], name="idx_bwhk_ten_fmt"),
            models.Index(fields=["tenant", "created_at"], name="idx_bwhk_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.endpoint_url[:40]})"

    def save(self, *args, **kwargs):
        if not self.secret_token:
            self.secret_token = f"whsec_{secrets.token_hex(24)}"
        super().save(*args, **kwargs)
