from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class CatalogLineageEdge(TenantNumbered):
    NUMBER_PREFIX = "BLIN"

    LINEAGE_TYPE_CHOICES = [
        ("table_level", "Table-to-Table Dataset Lineage"),
        ("column_level", "Column-to-Column Granular Lineage"),
        ("pipeline_transformation", "ETL Pipeline Transformation"),
        ("semantic_abstraction", "Semantic Model Logical Derivation"),
        ("report_consumption", "BI Report / Dashboard Query"),
    ]

    IMPACT_CRITICALITY_CHOICES = [
        ("low", "Low - Informational / Non-Breaking"),
        ("medium", "Medium - Team Reporting Impact"),
        ("high", "High - Key Operational Dependency"),
        ("critical", "Critical - Regulatory / Financial Lineage Break"),
    ]

    upstream_asset = models.ForeignKey(
        "bi.CatalogAsset",
        on_delete=models.CASCADE,
        related_name="downstream_edges",
        help_text="Source / upstream dataset producing data",
    )
    downstream_asset = models.ForeignKey(
        "bi.CatalogAsset",
        on_delete=models.CASCADE,
        related_name="upstream_edges",
        help_text="Target / downstream dataset consuming data",
    )

    lineage_type = models.CharField(
        max_length=30,
        choices=LINEAGE_TYPE_CHOICES,
        default="table_level",
    )
    upstream_column = models.CharField(
        max_length=120,
        blank=True,
        help_text="Specific source column name (for column-level lineage)",
    )
    downstream_column = models.CharField(
        max_length=120,
        blank=True,
        help_text="Specific target column name (for column-level lineage)",
    )
    transformation_rule = models.TextField(
        blank=True,
        help_text="SQL expression, aggregation formula, or conversion logic (e.g. SUM(amount_cur * fx_rate))",
    )

    etl_pipeline = models.ForeignKey(
        "bi.EtlPipeline",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_lineage_edges",
        help_text="Executing ETL pipeline if transformation is automated",
    )
    transformation_step = models.ForeignKey(
        "bi.TransformationStep",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_lineage_edges",
        help_text="Granular pipeline transformation step",
    )

    impact_criticality = models.CharField(
        max_length=20,
        choices=IMPACT_CRITICALITY_CHOICES,
        default="medium",
        help_text="Blast radius criticality if upstream schema breaks",
    )
    is_automated_extraction = models.BooleanField(
        default=True,
        help_text="True if automatically discovered via query log / ETL parser; False if manually defined",
    )
    last_verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_catalog_lineage_edge"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_blin_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "upstream_asset"], name="idx_blin_ten_up"),
            models.Index(fields=["tenant", "downstream_asset"], name="idx_blin_ten_down"),
            models.Index(fields=["tenant", "lineage_type"], name="idx_blin_ten_type"),
            models.Index(fields=["tenant", "impact_criticality"], name="idx_blin_ten_crit"),
            models.Index(fields=["tenant", "is_active"], name="idx_blin_ten_active"),
        ]

    def __str__(self):
        if "upstream_asset" in self._state.fields_cache:
            source = self.upstream_asset.code
        else:
            source = f"Asset #{self.upstream_asset_id}"
        if self.upstream_column:
            source += f".{self.upstream_column}"

        if "downstream_asset" in self._state.fields_cache:
            target = self.downstream_asset.code
        else:
            target = f"Asset #{self.downstream_asset_id}"
        if self.downstream_column:
            target += f".{self.downstream_column}"
        return f"{self.number} ({source} -> {target})"

    def get_absolute_url(self):
        return reverse("bi:catalog_lineage_edge_detail", kwargs={"pk": self.pk})
