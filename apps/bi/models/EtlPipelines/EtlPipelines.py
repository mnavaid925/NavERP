from apps.bi.models._base import TenantNumbered, models, settings


class EtlPipeline(TenantNumbered):
    NUMBER_PREFIX = "BETL"

    STATUS_CHOICES = [
        ("draft", "Draft / Configuring"),
        ("active", "Active / Ready"),
        ("paused", "Paused / Inactive"),
        ("deprecated", "Deprecated"),
        ("error", "Execution Error"),
    ]

    TRIGGER_TYPE_CHOICES = [
        ("manual", "Manual Trigger Only"),
        ("scheduled_cron", "Scheduled Cron / Time Window"),
        ("event_on_ingest", "Event-Driven (On Ingestion Completion)"),
        ("dependency_chained", "Dependency Chained (DAG Trigger)"),
    ]

    TARGET_LAYER_CHOICES = [
        ("staging", "Raw / Staging Buffer"),
        ("warehouse_fact", "Enterprise Warehouse Fact Table"),
        ("warehouse_dim", "Enterprise Warehouse Dimension Table"),
        ("data_mart", "Subject-Specific Data Mart"),
    ]

    name = models.CharField(max_length=150, help_text="Descriptive ETL/ELT pipeline name")
    description = models.TextField(blank=True)
    source_ingestion_pipeline = models.ForeignKey(
        "bi.IngestionPipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="downstream_etl_pipelines",
        help_text="Upstream ingestion pipeline producing staging data",
    )
    source_staging_table = models.CharField(
        max_length=150,
        blank=True,
        help_text="Source staging dataset or table, e.g. stg_accounting_invoices",
    )
    target_table = models.CharField(
        max_length=150,
        help_text="Target analytical table or mart table, e.g. fct_monthly_sales",
    )
    target_layer = models.CharField(
        max_length=30,
        choices=TARGET_LAYER_CHOICES,
        default="warehouse_fact",
    )
    trigger_type = models.CharField(
        max_length=30,
        choices=TRIGGER_TYPE_CHOICES,
        default="scheduled_cron",
    )
    cron_expression = models.CharField(
        max_length=60,
        blank=True,
        help_text="Cron expression for scheduled executions, e.g. 0 2 * * *",
    )
    upstream_dependencies = models.JSONField(
        default=list,
        blank=True,
        help_text="List of upstream BETL pipeline numbers or IDs required before trigger",
    )
    retry_policy = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configurable retry rules: max_retries, retry_delay_seconds, backoff_factor",
    )
    sla_timeout_seconds = models.PositiveIntegerField(
        default=3600,
        help_text="Maximum allowed runtime in seconds before SLA breach is flagged",
    )
    alert_on_sla_miss = models.BooleanField(
        default=True,
        help_text="Dispatch system alert when SLA runtime threshold is breached",
    )
    alert_rule = models.ForeignKey(
        "core.AlertRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_etl_pipelines",
        help_text="Linked observability alert policy",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    canvas_layout = models.JSONField(
        default=dict,
        blank=True,
        help_text="Visual pipeline designer node coordinates and layout metadata",
    )
    active_version = models.ForeignKey(
        "bi.EtlPipelineVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Currently published active DAG version",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_etl_pipelines_created",
    )

    class Meta:
        db_table = "bi_etl_pipeline"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_betl_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "trigger_type"], name="idx_betl_ten_stat_trig"),
            models.Index(fields=["tenant", "target_layer"], name="idx_betl_ten_tgt_layer"),
            models.Index(fields=["tenant", "name"], name="idx_betl_ten_name"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"
