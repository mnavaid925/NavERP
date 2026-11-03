from apps.bi.models._base import TenantNumbered, models


class TransformationStep(TenantNumbered):
    NUMBER_PREFIX = "BTRN"

    STEP_TYPE_CHOICES = [
        ("join", "Relational Join (Inner/Left/Right/Full/Cross)"),
        ("aggregate", "Grouped Aggregation (Sum/Avg/Count/Min/Max)"),
        ("pivot", "Matrix Pivot (Rows to Columns)"),
        ("unpivot", "Matrix Unpivot (Columns to Rows)"),
        ("cast", "Type Casting & Schema Sanitization"),
        ("filter", "Row Filter & Conditional Split"),
        ("derived_column", "Derived Calculated Expression"),
        ("lookup_enrichment", "Master Data Lookup Enrichment"),
        ("deduplicate", "Row Deduplication & Distinct"),
        ("business_rule", "Reusable ERP Business Rule Transform"),
    ]

    STATUS_CHOICES = [
        ("active", "Active / Enabled"),
        ("disabled", "Disabled / Skipped"),
        ("draft", "Draft / Configuring"),
    ]

    pipeline = models.ForeignKey(
        "bi.EtlPipeline",
        on_delete=models.CASCADE,
        related_name="steps",
    )
    name = models.CharField(max_length=150, help_text="Transform step label or operation name")
    step_type = models.CharField(
        max_length=30,
        choices=STEP_TYPE_CHOICES,
        default="derived_column",
    )
    sequence = models.PositiveIntegerField(
        default=1,
        help_text="Topological execution order sequence within DAG",
    )
    upstream_step_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of prerequisite step numbers/IDs feeding input into this node",
    )
    step_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed transform specifications: join keys, aggregation metrics, formulas, cast rules",
    )
    mapping_template = models.ForeignKey(
        "core.MappingTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etl_transformation_steps",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    is_blocking = models.BooleanField(
        default=True,
        help_text="If True, step failure halts entire pipeline execution",
    )
    canvas_x = models.IntegerField(default=100, help_text="X-coordinate on visual DAG canvas")
    canvas_y = models.IntegerField(default=100, help_text="Y-coordinate on visual DAG canvas")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "bi_transformation_step"
        ordering = ["pipeline", "sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_btrn_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "pipeline", "sequence"], name="idx_btrn_ten_pipe_seq"),
            models.Index(fields=["tenant", "step_type", "status"], name="idx_btrn_ten_type_stat"),
        ]

    def __str__(self):
        return f"{self.number} — #{self.sequence} {self.name} ({self.get_step_type_display()})"
