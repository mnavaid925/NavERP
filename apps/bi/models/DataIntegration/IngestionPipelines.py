import secrets

from django.db import models

from apps.bi.models._base import TenantNumbered


class IngestionPipeline(TenantNumbered):
    NUMBER_PREFIX = "BING"

    INGESTION_MODE_CHOICES = [
        ("batch_scheduled", "Scheduled Batch"),
        ("micro_batch", "Micro-Batch (Near-Real-Time)"),
        ("real_time_webhook", "Real-Time Webhook Push"),
        ("manual_on_demand", "Manual On-Demand Only"),
    ]

    SCHEDULE_CADENCE_CHOICES = [
        ("manual", "Manual Trigger Only"),
        ("every_15_min", "Every 15 Minutes"),
        ("hourly", "Hourly"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("custom_cron", "Custom Cron Expression"),
    ]

    FILE_FORMAT_CHOICES = [
        ("none", "Not Applicable / Database Query"),
        ("csv", "CSV (Comma-Separated)"),
        ("tsv", "TSV (Tab-Separated)"),
        ("json", "JSON Array / Objects"),
        ("ndjson", "Newline-Delimited JSON"),
        ("excel", "Excel Spreadsheet (.xlsx)"),
        ("parquet", "Apache Parquet"),
    ]

    STATUS_CHOICES = [
        ("active", "Active / Scheduled"),
        ("paused", "Paused"),
        ("draft", "Draft / Configuring"),
        ("error", "Execution Error"),
    ]

    name = models.CharField(max_length=150, help_text="Pipeline identifier label")
    connector = models.ForeignKey(
        "bi.DataSourceConnector",
        on_delete=models.PROTECT,
        related_name="pipelines",
        help_text="Source connector used by this ingestion pipeline",
    )
    ingestion_mode = models.CharField(
        max_length=30,
        choices=INGESTION_MODE_CHOICES,
        default="batch_scheduled",
    )
    source_entity = models.CharField(
        max_length=150,
        help_text="Source table, collection, API endpoint, or ERP model identifier",
    )
    target_staging_table = models.CharField(
        max_length=150,
        help_text="Target analytical staging table, e.g. stg_accounting_invoices",
    )
    schedule_cadence = models.CharField(
        max_length=30,
        choices=SCHEDULE_CADENCE_CHOICES,
        default="daily",
    )
    cron_expression = models.CharField(max_length=60, blank=True)
    file_format = models.CharField(
        max_length=20,
        choices=FILE_FORMAT_CHOICES,
        default="none",
    )
    file_parsing_options = models.JSONField(
        default=dict,
        blank=True,
        help_text="delimiter, quote_char, has_header, skip_rows, encoding, path_pattern",
    )
    webhook_token = models.CharField(
        max_length=64,
        blank=True,
        unique=True,
        null=True,
        db_index=True,
        help_text="Unique secret URL slug for inbound webhook ingress",
    )
    webhook_secret = models.CharField(
        max_length=128,
        blank=True,
        help_text="HMAC verification secret or shared token",
    )
    rate_limit_policy = models.ForeignKey(
        "core.RateLimitPolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_pipelines",
    )
    mapping_template = models.ForeignKey(
        "core.MappingTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_pipelines",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bing_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "ingestion_mode"], name="idx_bing_ten_stat_mode"),
            models.Index(fields=["tenant", "connector"], name="idx_bing_ten_connector"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} -> {self.target_staging_table}"

    def save(self, *args, **kwargs):
        if self.ingestion_mode == "real_time_webhook" and not self.webhook_token:
            self.webhook_token = secrets.token_hex(24)
            if not self.webhook_secret:
                self.webhook_secret = secrets.token_hex(32)
        elif self.webhook_token == "":
            self.webhook_token = None
        super().save(*args, **kwargs)
