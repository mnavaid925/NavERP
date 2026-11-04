from django.db import models

from apps.bi.models._base import TenantNumbered


class LakehouseZone(TenantNumbered):
    NUMBER_PREFIX = "BLHZ"

    ZONE_TYPE_CHOICES = [
        ("bronze", "Bronze (Raw Ingestion / Append-Only Landing)"),
        ("silver", "Silver (Curated / Cleaned / Conformed Master)"),
        ("gold", "Gold (Aggregated / Dimensional Star Schemas / Business-Ready)"),
        ("sandbox", "Sandbox (Ad-Hoc Exploration / Data Science)"),
    ]

    STORAGE_BACKEND_CHOICES = [
        ("internal_db", "Internal Relational Database"),
        ("aws_s3", "Amazon Web Services S3"),
        ("azure_blob", "Microsoft Azure Blob / ADLS Gen2"),
        ("gcs", "Google Cloud Storage"),
        ("local_filesystem", "Local Dedicated Shared Storage"),
    ]

    DEFAULT_FORMAT_CHOICES = [
        ("relational_table", "Relational Table / View"),
        ("parquet", "Apache Parquet Columnar File"),
        ("delta_lake", "Delta Lake (Delta-Parquet + Log)"),
        ("iceberg", "Apache Iceberg Table Format"),
        ("csv_compressed", "Compressed CSV / Gzip"),
    ]

    name = models.CharField(max_length=150, help_text="Medallion zone display name")
    code = models.SlugField(max_length=50, help_text="Unique slug code for zone identification")
    zone_type = models.CharField(max_length=25, choices=ZONE_TYPE_CHOICES, default="bronze")
    storage_backend = models.CharField(max_length=30, choices=STORAGE_BACKEND_CHOICES, default="internal_db")
    default_format = models.CharField(max_length=25, choices=DEFAULT_FORMAT_CHOICES, default="relational_table")
    base_uri_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Base storage URI endpoint or bucket path prefix (e.g. s3://warehouse-lake/bronze/)",
    )
    is_read_only = models.BooleanField(
        default=False,
        help_text="Immutable write protection for raw landing layers",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_lakehouse_zone"
        ordering = ["zone_type", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_blhz_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_blhz_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "zone_type"], name="idx_blhz_ten_zone"),
            models.Index(fields=["tenant", "storage_backend"], name="idx_blhz_ten_backend"),
            models.Index(fields=["tenant", "is_active"], name="idx_blhz_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"
