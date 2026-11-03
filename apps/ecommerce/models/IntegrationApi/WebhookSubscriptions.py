from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class WebhookSubscription(TenantNumbered):
    NUMBER_PREFIX = "EWBS"

    EVENT_TOPIC_CHOICES = [
        ("order.created", "Order Created"),
        ("order.paid", "Order Payment Captured"),
        ("order.fulfilled", "Order Fulfilled / Shipped"),
        ("order.cancelled", "Order Cancelled"),
        ("order.refunded", "Order Refund Issued"),
        ("inventory.low_stock", "Inventory Low Stock Warning"),
        ("inventory.updated", "Inventory Levels Updated"),
        ("product.created", "Product Created"),
        ("product.updated", "Product Updated"),
        ("customer.registered", "Customer Account Registered"),
        ("dispute.opened", "Chargeback Dispute Opened"),
        ("all_events", "All Commerce Events (* wildcard)"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Delivering"),
        ("paused", "Paused by Administrator"),
        ("disabled", "Disabled / Inactive"),
        ("circuit_broken", "Circuit Broken (Failure Threshold Exceeded)"),
    ]

    PAYLOAD_FORMAT_CHOICES = [
        ("json", "application/json"),
        ("form_encoded", "application/x-www-form-urlencoded"),
    ]

    name = models.CharField(
        max_length=255,
        help_text="Friendly webhook subscriber description",
    )
    target_url = models.CharField(
        max_length=500,
        help_text="Destination HTTPS endpoint URL to receive webhook delivery",
    )
    event_topic = models.CharField(
        max_length=50,
        choices=EVENT_TOPIC_CHOICES,
        default="order.created",
        help_text="Commerce domain event topic triggering delivery",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Delivery state and circuit breaker posture",
    )
    secret_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="HMAC-SHA256 signature verification key for X-NavERP-Signature header",
    )
    payload_format = models.CharField(
        max_length=20,
        choices=PAYLOAD_FORMAT_CHOICES,
        default="json",
        help_text="HTTP content-type formatting",
    )
    custom_headers = models.TextField(
        blank=True,
        default="{}",
        help_text="JSON dictionary of custom HTTP request headers",
    )
    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Consecutive delivery errors before triggering circuit breaker",
    )
    max_consecutive_failures = models.IntegerField(
        default=5,
        help_text="Threshold of failed attempts before auto-tripping circuit breaker",
    )
    last_delivery_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of most recent delivery attempt",
    )
    last_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP response code returned from target endpoint",
    )
    last_error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message or trace from latest failed delivery",
    )
    total_delivered_count = models.IntegerField(
        default=0,
        help_text="Cumulative successfully delivered webhook events",
    )
    total_failed_count = models.IntegerField(
        default=0,
        help_text="Cumulative failed delivery attempts",
    )
    is_verify_ssl = models.BooleanField(
        default=True,
        help_text="Enforce strict TLS/SSL certificate validation on target endpoint",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Internal notes on webhook subscriber and consumer system",
    )

    class Meta:
        db_table = "ecommerce_webhook_subscription"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_ewbs_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_ewbs_ten_status"),
            models.Index(fields=["tenant", "event_topic"], name="idx_ewbs_ten_topic"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.event_topic})"
