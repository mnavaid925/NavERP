from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class IntegrationConnector(TenantNumbered):
    NUMBER_PREFIX = "BINT"

    CONNECTOR_TYPE_CHOICES = [
        ("internal_erp", "Internal NavERP Operational Module"),
        ("message_broker", "Streaming Message Queue / Event Bus"),
        ("saas_application", "Third-Party SaaS Application"),
        ("custom_api", "Custom REST/GraphQL Endpoint"),
    ]

    TARGET_SYSTEM_CHOICES = [
        ("erp_accounting", "Module 2: Accounting & Financial Ledger"),
        ("erp_hrm", "Module 3: Human Resource Management"),
        ("erp_scm", "Module 4: Supply Chain & Procurement"),
        ("erp_crm", "Module 1: CRM & Sales Management"),
        ("erp_inventory", "Module 5: Inventory & Warehouse"),
        ("kafka", "Apache Kafka Cluster"),
        ("rabbitmq", "RabbitMQ Message Broker"),
        ("aws_eventbridge", "AWS EventBridge Event Bus"),
        ("redis_streams", "Redis Streams Pub/Sub"),
        ("generic_webhook", "Generic HTTP/REST Gateway"),
    ]

    SYNC_DIRECTION_CHOICES = [
        ("inbound", "Inbound (Operational Data → BI Lakehouse)"),
        ("outbound", "Outbound (BI Intelligence → Operational Target)"),
        ("bidirectional", "Bidirectional (Continuous Closed-Loop)"),
    ]

    AUTH_TYPE_CHOICES = [
        ("internal_session", "Internal NavERP Direct Session"),
        ("api_key", "API Key Header"),
        ("bearer_token", "OAuth2 / Bearer Token"),
        ("basic_auth", "HTTP Basic Authentication"),
        ("iam_role", "AWS IAM Role / Cloud Identity"),
        ("tls_certificate", "Mutual TLS Certificate"),
    ]

    MESSAGE_FORMAT_CHOICES = [
        ("json", "Standard JSON"),
        ("avro", "Apache Avro (Schema Governed)"),
        ("protobuf", "Google Protocol Buffers"),
        ("cloudevents", "CloudEvents 1.0 Specification"),
    ]

    SYNC_INTERVAL_CHOICES = [
        ("realtime_event", "Real-Time Event Triggered"),
        ("every_minute", "Every Minute"),
        ("every_5_minutes", "Every 5 Minutes"),
        ("hourly", "Hourly"),
        ("daily", "Daily Scheduled"),
        ("manual", "Manual On-Demand Only"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Running"),
        ("paused", "Paused by Administrator"),
        ("error", "Failed / Error State"),
        ("maintenance", "Under Maintenance"),
    ]

    HEALTH_STATUS_CHOICES = [
        ("healthy", "Healthy (Heartbeat Normal)"),
        ("degraded", "Degraded (High Latency / Intermittent)"),
        ("unreachable", "Unreachable (Connection Refused)"),
        ("untested", "Untested Configuration"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, blank=True)
    description = models.TextField(blank=True)

    connector_type = models.CharField(
        max_length=40,
        choices=CONNECTOR_TYPE_CHOICES,
        default="internal_erp",
    )
    target_system = models.CharField(
        max_length=50,
        choices=TARGET_SYSTEM_CHOICES,
        default="erp_accounting",
    )
    sync_direction = models.CharField(
        max_length=30,
        choices=SYNC_DIRECTION_CHOICES,
        default="outbound",
    )

    connection_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Host connection parameters (bootstrap servers, topic name, batch size, timeout, flush interval)",
    )
    auth_type = models.CharField(
        max_length=40,
        choices=AUTH_TYPE_CHOICES,
        default="internal_session",
    )
    auth_credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text="Encrypted or masked credential parameters",
    )

    message_format = models.CharField(
        max_length=30,
        choices=MESSAGE_FORMAT_CHOICES,
        default="json",
    )
    sync_interval = models.CharField(
        max_length=30,
        choices=SYNC_INTERVAL_CHOICES,
        default="realtime_event",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="active",
    )
    health_status = models.CharField(
        max_length=30,
        choices=HEALTH_STATUS_CHOICES,
        default="healthy",
    )

    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    total_messages_processed = models.PositiveBigIntegerField(default=0)
    error_message = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_created_connectors",
    )

    class Meta:
        db_table = "bi_integration_connector"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bint_ten_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="bi_bint_ten_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bint_ten_stat"),
            models.Index(fields=["tenant", "connector_type"], name="idx_bint_ten_type"),
            models.Index(fields=["tenant", "target_system"], name="idx_bint_ten_target"),
            models.Index(fields=["tenant", "sync_interval"], name="idx_bint_ten_intv"),
            models.Index(fields=["tenant", "is_enabled"], name="idx_bint_ten_enb"),
            models.Index(fields=["tenant", "created_at"], name="idx_bint_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_target_system_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "connector"
            candidate = base_slug[:110]
            counter = 1
            qs = IntegrationConnector.objects.filter(tenant=self.tenant)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug=candidate).exists():
                candidate = f"{base_slug[:100]}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)
