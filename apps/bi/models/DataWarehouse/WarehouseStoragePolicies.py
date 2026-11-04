from django.db import models

from apps.bi.models._base import TenantNumbered


class WarehouseStoragePolicy(TenantNumbered):
    NUMBER_PREFIX = "BWSP"

    PARTITION_STRATEGY_CHOICES = [
        ("none", "None (Unpartitioned Flat Table)"),
        ("range_time", "Range / Time-Based (Date/Timestamp)"),
        ("range_numeric", "Numeric Range (Integer Buckets)"),
        ("hash", "Hash / Slices (Distributed Keys)"),
        ("list_category", "List / Categorical (Region/Branch/Status)"),
    ]

    PARTITION_GRANULARITY_CHOICES = [
        ("hour", "Hourly"),
        ("day", "Daily"),
        ("month", "Monthly"),
        ("quarter", "Quarterly"),
        ("year", "Yearly"),
    ]

    COMPRESSION_CODEC_CHOICES = [
        ("none", "None (Uncompressed)"),
        ("snappy", "Snappy (Fast Decompression)"),
        ("zstd", "Zstandard (ZSTD Balanced High Ratio)"),
        ("lz4", "LZ4 (Ultra-Low Latency)"),
        ("gzip", "Gzip (Maximum Compression Ratio)"),
    ]

    VACUUM_CADENCE_CHOICES = [
        ("daily", "Daily Vacuum & Compaction"),
        ("weekly", "Weekly Vacuum & Compaction"),
        ("monthly", "Monthly Cleanup"),
        ("manual", "Manual Trigger Only"),
    ]

    name = models.CharField(max_length=150, help_text="Storage and lifecycle policy label")
    partition_strategy = models.CharField(
        max_length=30,
        choices=PARTITION_STRATEGY_CHOICES,
        default="range_time",
        help_text="Physical table partitioning layout",
    )
    partition_key = models.CharField(
        max_length=100,
        blank=True,
        help_text="Column name used as partition key (e.g. posting_date, created_at)",
    )
    partition_granularity = models.CharField(
        max_length=25,
        choices=PARTITION_GRANULARITY_CHOICES,
        default="month",
        help_text="Time slice granularity for range partitions",
    )
    compression_codec = models.CharField(
        max_length=25,
        choices=COMPRESSION_CODEC_CHOICES,
        default="zstd",
        help_text="Columnar compression codec encoding",
    )
    enable_zone_maps = models.BooleanField(
        default=True,
        help_text="Track min/max column statistics for query pruning and block skipping",
    )
    hot_tier_days = models.PositiveIntegerField(
        default=90,
        help_text="Days retained in high-performance NVMe/SSD storage",
    )
    warm_tier_days = models.PositiveIntegerField(
        default=365,
        help_text="Days retained in standard warm storage before cooling",
    )
    cold_tier_days = models.PositiveIntegerField(
        default=2555,
        help_text="Days retained in deep cold archive (2555 = 7 years statutory)",
    )
    time_travel_days = models.PositiveIntegerField(
        default=7,
        help_text="Historical snapshot retention window for time-travel queries (0-90 days)",
    )
    auto_purge_enabled = models.BooleanField(
        default=False,
        help_text="Automatically drop partitions older than cold retention threshold",
    )
    vacuum_cadence = models.CharField(
        max_length=25,
        choices=VACUUM_CADENCE_CHOICES,
        default="weekly",
        help_text="Cadence for automated table vacuum, compaction, and dead tuple reclamation",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default policy automatically applied to newly registered warehouse tables",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_warehouse_storage_policy"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bwsp_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "name"], name="idx_bwsp_ten_name"),
            models.Index(fields=["tenant", "partition_strategy"], name="idx_bwsp_ten_part"),
            models.Index(fields=["tenant", "is_default"], name="idx_bwsp_ten_def"),
            models.Index(fields=["tenant", "is_active"], name="idx_bwsp_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"
