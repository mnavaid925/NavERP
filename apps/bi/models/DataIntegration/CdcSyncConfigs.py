from django.db import models

from apps.bi.models._base import TenantNumbered


class CdcSyncConfig(TenantNumbered):
    NUMBER_PREFIX = "BCDC"

    CAPTURE_METHOD_CHOICES = [
        ("log_based", "Log-Based CDC (WAL / Binlog / Redo)"),
        ("query_timestamp", "Query Timestamp Cursor (Modified Date)"),
        ("query_incrementing_id", "Query Incrementing Sequence (Auto-Increment / Sequence ID)"),
        ("full_snapshot", "Full Snapshot Table Scan"),
    ]

    SYNC_MODE_CHOICES = [
        ("full_refresh_overwrite", "Full Refresh Overwrite"),
        ("full_refresh_append", "Full Refresh Append"),
        ("incremental_append", "Incremental Append (Change Log)"),
        ("incremental_deduped", "Incremental Deduped (Upsert by Primary Key)"),
    ]

    SCHEMA_DRIFT_CHOICES = [
        ("auto_propagate", "Auto-Propagate New Columns"),
        ("detect_and_warn", "Detect & Warn (Flag Log)"),
        ("block_and_pause", "Block & Pause Pipeline"),
    ]

    pipeline = models.OneToOneField(
        "bi.IngestionPipeline",
        on_delete=models.CASCADE,
        related_name="cdc_config",
        help_text="Pipeline orchestrated by this CDC configuration",
    )
    capture_method = models.CharField(
        max_length=30,
        choices=CAPTURE_METHOD_CHOICES,
        default="query_timestamp",
        help_text="Delta detection mechanism for changed source rows",
    )
    sync_mode = models.CharField(
        max_length=30,
        choices=SYNC_MODE_CHOICES,
        default="incremental_deduped",
        help_text="Target loading strategy for CDC event streams",
    )
    primary_key_fields = models.CharField(
        max_length=150,
        default="id",
        help_text="Comma-separated primary key columns for deduplication and upserts",
    )
    cursor_field = models.CharField(
        max_length=100,
        blank=True,
        default="updated_at",
        help_text="Source field used as high-water mark cursor (e.g. updated_at, timestamp, sequence id)",
    )
    last_cursor_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Current committed high-water mark offset or timestamp",
    )
    last_checkpoint_at = models.DateTimeField(null=True, blank=True)
    schema_drift_policy = models.CharField(
        max_length=25,
        choices=SCHEMA_DRIFT_CHOICES,
        default="detect_and_warn",
        help_text="Action taken when source schema columns change",
    )
    capture_deletes = models.BooleanField(
        default=True,
        help_text="Capture and flag deleted records in destination staging",
    )
    soft_delete_field = models.CharField(
        max_length=60,
        default="is_deleted",
        blank=True,
        help_text="Column name in source indicating soft-deletion",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bcdc_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "capture_method", "sync_mode"], name="idx_bcdc_ten_meth_mode"),
        ]

    def __str__(self):
        return f"{self.number} — CDC for {self.pipeline.name} ({self.get_sync_mode_display()})"
