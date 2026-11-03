from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class IntegrationSyncJob(TenantNumbered):
    NUMBER_PREFIX = "ESYJ"

    SYNC_ENTITY_CHOICES = [
        ("order_to_cash", "Order-to-Cash (Orders & Invoices)"),
        ("inventory_levels", "Inventory Levels & Stock Availability"),
        ("catalog_products", "Product Catalog & Pricing"),
        ("customer_profiles", "Customer Profiles & Contacts"),
        ("shipment_tracking", "Shipments & Tracking Numbers"),
        ("payment_settlement", "Payment Settlements & Payouts"),
        ("marketing_events", "Marketing Events & Triggers"),
        ("custom_payload", "Custom JSON Payload Sync"),
    ]

    DIRECTION_CHOICES = [
        ("inbound", "Inbound (External -> NavERP)"),
        ("outbound", "Outbound (NavERP -> External)"),
        ("bidirectional", "Bidirectional Sync"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending / Queued"),
        ("running", "Running / In-Progress"),
        ("completed", "Completed Successfully"),
        ("failed", "Failed"),
        ("partial_success", "Partial Success with Errors"),
        ("cancelled", "Cancelled"),
    ]

    TRIGGER_TYPE_CHOICES = [
        ("scheduled", "Scheduled Polling / Cron"),
        ("manual", "Manual Trigger by Staff"),
        ("webhook", "Real-Time Inbound Webhook"),
        ("event_driven", "Event-Driven Platform Action"),
    ]

    connector = models.ForeignKey(
        "ecommerce.EcommerceConnector",
        on_delete=models.CASCADE,
        related_name="sync_jobs",
        help_text="Target connector providing integration endpoint",
    )
    sync_entity = models.CharField(
        max_length=40,
        choices=SYNC_ENTITY_CHOICES,
        default="order_to_cash",
        help_text="Data domain / entity synchronized in this job execution",
    )
    direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        default="outbound",
        help_text="Flow direction of synchronized data",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Execution state of sync job",
    )
    trigger_type = models.CharField(
        max_length=25,
        choices=TRIGGER_TYPE_CHOICES,
        default="manual",
        help_text="What initiated this synchronization run",
    )
    batch_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Sync execution batch UUID or correlation ID",
    )
    records_total = models.IntegerField(
        default=0,
        help_text="Total number of records identified for sync",
    )
    records_processed = models.IntegerField(
        default=0,
        help_text="Total records processed so far",
    )
    records_succeeded = models.IntegerField(
        default=0,
        help_text="Records successfully transferred and acknowledged",
    )
    records_failed = models.IntegerField(
        default=0,
        help_text="Records that produced errors",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Job execution start timestamp",
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Job completion timestamp",
    )
    duration_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total runtime in seconds",
    )
    error_summary = models.TextField(
        blank=True,
        default="",
        help_text="Detailed failure trace or diagnostic log",
    )
    payload_preview = models.TextField(
        blank=True,
        default="",
        help_text="Sample payload summary or request body",
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Current retry attempt number",
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum retry attempts allowed",
    )
    parent_job = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_retries",
        help_text="Parent sync job if this execution is a retry",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triggered_sync_jobs",
        help_text="Staff member who manually invoked the sync job",
    )

    class Meta:
        db_table = "ecommerce_integration_sync_job"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esyj_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_esyj_ten_status"),
            models.Index(fields=["tenant", "connector"], name="idx_esyj_ten_conn"),
            models.Index(fields=["tenant", "sync_entity"], name="idx_esyj_ten_entity"),
            models.Index(fields=["tenant", "started_at"], name="idx_esyj_ten_started"),
            models.Index(fields=["tenant", "-created_at"], name="idx_esyj_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_sync_entity_display()} ({self.get_status_display()})"
