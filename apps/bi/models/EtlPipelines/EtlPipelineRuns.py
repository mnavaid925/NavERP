from decimal import Decimal

from django.utils import timezone

from apps.bi.models._base import TenantNumbered, models


class EtlPipelineRun(TenantNumbered):
    NUMBER_PREFIX = "BEXR"

    TRIGGER_TYPE_CHOICES = [
        ("manual", "Manual User Trigger"),
        ("scheduled", "Automated Scheduled Cadence"),
        ("event_upstream", "Upstream Ingestion Event"),
        ("backfill", "Historical Partition Backfill"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending / Enqueued"),
        ("queued", "Queued in Work Pool"),
        ("running", "Running Transformations"),
        ("completed", "Completed Successfully"),
        ("warning", "Completed with Non-Fatal Warnings"),
        ("failed", "Execution Failed"),
        ("cancelled", "Cancelled by User"),
        ("timed_out", "Timed Out (SLA Breached)"),
    ]

    pipeline = models.ForeignKey(
        "bi.EtlPipeline",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    version = models.ForeignKey(
        "bi.EtlPipelineVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
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
    records_in = models.PositiveIntegerField(
        default=0,
        help_text="Total source staging records extracted",
    )
    records_transformed = models.PositiveIntegerField(
        default=0,
        help_text="Records successfully processed through transformations",
    )
    records_out = models.PositiveIntegerField(
        default=0,
        help_text="Records successfully written to target table",
    )
    records_rejected = models.PositiveIntegerField(
        default=0,
        help_text="Records failing filters, joins, or type assertions",
    )
    bytes_processed = models.BigIntegerField(
        default=0,
        help_text="Total data volume processed in bytes",
    )
    sla_missed = models.BooleanField(
        default=False,
        help_text="Flagged True if duration exceeded pipeline SLA threshold",
    )
    is_backfill = models.BooleanField(
        default=False,
        help_text="True if run executes a historical partition backfill",
    )
    backfill_range_start = models.DateTimeField(null=True, blank=True)
    backfill_range_end = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    step_progress = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary of step execution progress, status, and row counts",
    )
    error_message = models.TextField(blank=True)
    execution_log = models.TextField(blank=True)

    class Meta:
        db_table = "bi_etl_pipeline_run"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bexr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "pipeline", "started_at"], name="idx_bexr_ten_pipe_start"),
            models.Index(fields=["tenant", "status", "started_at"], name="idx_bexr_ten_stat_start"),
        ]

    def __str__(self):
        return f"{self.number} — {self.pipeline.name} ({self.get_status_display()} [{self.started_at.strftime('%Y-%m-%d %H:%M')}])"
