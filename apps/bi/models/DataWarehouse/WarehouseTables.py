from decimal import Decimal

from django.db import models

from apps.bi.models._base import TenantNumbered


class WarehouseTable(TenantNumbered):
    NUMBER_PREFIX = "BDWT"

    TABLE_TYPE_CHOICES = [
        ("fact", "Fact Table (Transactional / Periodic Metrics)"),
        ("dimension", "Dimension Table (Contextual Attributes & Master Data)"),
        ("aggregate", "Aggregate Table (Pre-Calculated Summary Rollups)"),
        ("bridge", "Bridge Table (Many-to-Many Disambiguation)"),
        ("staging", "Staging / Transient Target Table"),
    ]

    SCHEMA_TYPE_CHOICES = [
        ("star", "Star Schema (Direct Joins)"),
        ("snowflake", "Snowflake Schema (Normalized Sub-Dimensions)"),
        ("flat", "Flat / Denormalized Wide Table"),
        ("medallion", "Medallion Delta Format"),
    ]

    GRAIN_CHOICES = [
        ("transaction", "Transactional (One row per business event)"),
        ("daily_snapshot", "Daily Periodic Snapshot"),
        ("monthly_snapshot", "Monthly Periodic Snapshot"),
        ("accumulating_snapshot", "Accumulating Milestone Snapshot"),
        ("entity_state", "Entity Current State (Dimension)"),
    ]

    name = models.CharField(max_length=150, help_text="Human-friendly dataset name")
    table_name = models.CharField(
        max_length=100,
        help_text="Physical SQL table identifier (e.g. fact_gl_journal_entries, dim_customers)",
    )
    table_type = models.CharField(max_length=25, choices=TABLE_TYPE_CHOICES, default="fact")
    schema_type = models.CharField(max_length=25, choices=SCHEMA_TYPE_CHOICES, default="star")
    grain = models.CharField(max_length=30, choices=GRAIN_CHOICES, default="transaction")

    lakehouse_zone = models.ForeignKey(
        "bi.LakehouseZone",
        on_delete=models.PROTECT,
        related_name="tables",
        help_text="Assigned lakehouse medallion storage tier",
    )
    data_mart = models.ForeignKey(
        "bi.DataMart",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tables",
        help_text="Optional departmental data mart domain binding",
    )
    storage_policy = models.ForeignKey(
        "bi.WarehouseStoragePolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tables",
        help_text="Partitioning, compression, and lifecycle tiering policy",
    )

    primary_key_column = models.CharField(
        max_length=100,
        default="id",
        help_text="Surrogate primary key column name (e.g. entry_sk, customer_sk)",
    )
    natural_key_column = models.CharField(
        max_length=100,
        blank=True,
        help_text="Business natural key column (e.g. journal_number, customer_code)",
    )
    is_conformed_dimension = models.BooleanField(
        default=False,
        help_text="Indicates this dimension is conformed across multiple subject areas and business processes",
    )
    schema_definition = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured column definitions list: [{'name': '...', 'type': '...', 'nullable': bool, 'description': '...'}]",
    )

    row_count = models.BigIntegerField(default=0, help_text="Analyzed row count")
    compressed_bytes = models.BigIntegerField(default=0, help_text="Estimated storage footprint in bytes")
    compression_ratio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="Effective compression ratio (e.g. 3.45x)",
    )
    last_analyzed_at = models.DateTimeField(null=True, blank=True)

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_warehouse_table"
        ordering = ["table_type", "table_name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "table_name"], name="bi_bdwt_tenant_tbl_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdwt_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "table_type"], name="idx_bdwt_ten_type"),
            models.Index(fields=["tenant", "lakehouse_zone"], name="idx_bdwt_ten_zone"),
            models.Index(fields=["tenant", "data_mart"], name="idx_bdwt_ten_mart"),
            models.Index(fields=["tenant", "storage_policy"], name="idx_bdwt_ten_policy"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdwt_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.table_name})"

    def generate_ddl_sql(self):
        columns = self.schema_definition or []
        col_lines = []

        if self.primary_key_column:
            col_lines.append(f"    {self.primary_key_column} BIGINT PRIMARY KEY")

        for col in columns:
            name = col.get("name", "").strip()
            if not name or name == self.primary_key_column:
                continue
            col_type = col.get("type", "VARCHAR(255)").upper()
            nullable = "" if col.get("nullable", True) else " NOT NULL"
            col_lines.append(f"    {name} {col_type}{nullable}")

        col_def_str = ",\n".join(col_lines) if col_lines else f"    {self.primary_key_column} BIGINT PRIMARY KEY"

        partition_clause = ""
        if self.storage_policy and self.storage_policy.partition_strategy != "none" and self.storage_policy.partition_key:
            partition_clause = f"\nPARTITION BY RANGE ({self.storage_policy.partition_key});"
        else:
            partition_clause = ";"

        comment_block = f"-- Table: {self.table_name}\n-- Type: {self.get_table_type_display()} | Schema: {self.get_schema_type_display()} | Grain: {self.get_grain_display()}\n"
        create_stmt = f"CREATE TABLE IF NOT EXISTS {self.table_name} (\n{col_def_str}\n){partition_clause}"
        return f"{comment_block}{create_stmt}"
