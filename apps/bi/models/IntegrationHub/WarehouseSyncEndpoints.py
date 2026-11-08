from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class WarehouseSyncEndpoint(TenantNumbered):
    NUMBER_PREFIX = "BSNC"

    TARGET_WAREHOUSE_CHOICES = [
        ("snowflake", "Snowflake Cloud Data Warehouse"),
        ("google_bigquery", "Google BigQuery"),
        ("aws_redshift", "Amazon Redshift"),
        ("databricks_unity", "Databricks Unity Catalog"),
        ("power_bi_semantic_model", "Microsoft Power BI Semantic Model"),
        ("tableau_hyper", "Tableau Cloud / Server Hyper Extract"),
        ("looker_lookml", "Google Cloud Looker (LookML Feed)"),
    ]

    SYNC_MODE_CHOICES = [
        ("incremental_merge", "Incremental Upsert (Merge on Primary Key)"),
        ("full_refresh", "Full Overwrite (Truncate & Replace)"),
        ("append_only", "Append-Only (Time-Series Event Log)"),
        ("delta_sharing", "Delta Sharing Open Protocol Feed"),
        ("direct_query_federation", "Direct Query Virtualization View"),
    ]

    AUTH_METHOD_CHOICES = [
        ("service_account_key", "Service Account Key (JSON / PEM)"),
        ("snowflake_keypair", "Snowflake Key-Pair RSA Authentication"),
        ("oauth2_token", "OAuth2 Client Credentials Grant"),
        ("iam_role_arn", "AWS IAM Role ARN Delegation"),
        ("personal_access_token", "Personal Access Token"),
    ]

    SYNC_SCHEDULE_CHOICES = [
        ("hourly", "Hourly Sync"),
        ("every_4_hours", "Every 4 Hours"),
        ("daily", "Daily Sync (Nightly)"),
        ("weekly", "Weekly Sync"),
        ("event_triggered", "Triggered by ETL Pipeline Finish"),
        ("manual", "Manual Execution Only"),
    ]

    STATUS_CHOICES = [
        ("idle", "Idle (Scheduled)"),
        ("syncing", "Syncing in Progress"),
        ("success", "Last Sync Succeeded"),
        ("error", "Last Sync Failed"),
        ("disabled", "Sync Disabled"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, blank=True)

    target_warehouse = models.CharField(
        max_length=40,
        choices=TARGET_WAREHOUSE_CHOICES,
        default="snowflake",
    )
    sync_mode = models.CharField(
        max_length=40,
        choices=SYNC_MODE_CHOICES,
        default="incremental_merge",
    )

    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warehouse_syncs",
        help_text="Governed source semantic model to export",
    )
    data_mart = models.ForeignKey(
        "bi.DataMart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warehouse_syncs",
        help_text="Governed analytical data mart to synchronize",
    )

    destination_database = models.CharField(
        max_length=150,
        blank=True,
        help_text="Target cloud warehouse database name (e.g. ANALYTICS_PROD)",
    )
    destination_schema = models.CharField(
        max_length=150,
        blank=True,
        help_text="Target schema name (e.g. NAVERP_EXPORTS)",
    )
    destination_table = models.CharField(
        max_length=150,
        help_text="Target table, extract, or dataset name (e.g. DIM_CUSTOMERS)",
    )

    connection_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cloud warehouse parameters (account identifier, warehouse name, role, workspace id)",
    )
    auth_method = models.CharField(
        max_length=40,
        choices=AUTH_METHOD_CHOICES,
        default="service_account_key",
    )
    sync_schedule = models.CharField(
        max_length=30,
        choices=SYNC_SCHEDULE_CHOICES,
        default="daily",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="idle",
    )

    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_duration_ms = models.PositiveIntegerField(default=0)
    last_rows_synced = models.PositiveIntegerField(default=0)
    total_rows_synced = models.PositiveBigIntegerField(default=0)
    last_error_message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_warehouse_syncs",
    )

    class Meta:
        db_table = "bi_warehouse_sync_endpoint"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bsnc_ten_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="bi_bsnc_ten_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bsnc_ten_stat"),
            models.Index(fields=["tenant", "target_warehouse"], name="idx_bsnc_ten_wh"),
            models.Index(fields=["tenant", "semantic_model"], name="idx_bsnc_ten_sem"),
            models.Index(fields=["tenant", "data_mart"], name="idx_bsnc_ten_mart"),
            models.Index(fields=["tenant", "sync_mode"], name="idx_bsnc_ten_mode"),
            models.Index(fields=["tenant", "sync_schedule"], name="idx_bsnc_ten_sched"),
            models.Index(fields=["tenant", "is_active"], name="idx_bsnc_ten_act"),
            models.Index(fields=["tenant", "created_at"], name="idx_bsnc_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} -> {self.get_target_warehouse_display()}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "warehouse-sync"
            candidate = base_slug[:110]
            counter = 1
            qs = WarehouseSyncEndpoint.objects.filter(tenant=self.tenant)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug=candidate).exists():
                candidate = f"{base_slug[:100]}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)
