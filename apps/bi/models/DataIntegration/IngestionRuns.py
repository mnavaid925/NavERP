from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.bi.models._base import TenantNumbered


class IngestionRun(TenantNumbered):
    NUMBER_PREFIX = "BIJR"

    TRIGGER_TYPE_CHOICES = [
        ("scheduled", "Automated Scheduled Cadence"),
        ("manual", "Manual User Trigger"),
        ("webhook", "Inbound Webhook Event"),
        ("cdc_stream", "CDC Log Stream Micro-Batch"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending / Enqueued"),
        ("running", "Running / Ingesting"),
        ("completed", "Completed Successfully"),
        ("warning", "Completed with Warnings"),
        ("failed", "Execution Failed"),
        ("cancelled", "Cancelled by User"),
    ]

    pipeline = models.ForeignKey(
        "bi.IngestionPipeline",
        on_delete=models.CASCADE,
        related_name="runs",
        help_text="Pipeline executed during this ingestion run",
    )
    trigger_type = models.CharField(
        max_length=25,
        choices=TRIGGER_TYPE_CHOICES,
        default="manual",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    records_extracted = models.PositiveIntegerField(default=0)
    records_inserted = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_rejected = models.PositiveIntegerField(default=0)
    bytes_transferred = models.BigIntegerField(default=0)
    committed_cursor = models.CharField(max_length=255, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    log_summary = models.TextField(blank=True, help_text="Diagnostic execution log messages")

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bijr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "started_at"], name="idx_bijr_ten_stat_start"),
            models.Index(fields=["tenant", "pipeline", "started_at"], name="idx_bijr_ten_pipe_start"),
        ]

    def __str__(self):
        return f"{self.number} — {self.pipeline.name} [{self.get_status_display()}]"
