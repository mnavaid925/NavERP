from apps.bi.models._base import TenantNumbered, models, settings


class EtlPipelineVersion(TenantNumbered):
    NUMBER_PREFIX = "BPVR"

    ENVIRONMENT_CHOICES = [
        ("development", "Development (Dev Sandbox)"),
        ("staging", "Staging / Pre-Production (QA)"),
        ("production", "Production (Live Analytical DWH)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Version"),
        ("published", "Published / Active"),
        ("archived", "Archived / Historical"),
        ("rolled_back", "Rolled Back"),
    ]

    pipeline = models.ForeignKey(
        "bi.EtlPipeline",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.CharField(
        max_length=20,
        default="v1.0.0",
        help_text="Semantic version string, e.g. v1.0.0, v1.1.0",
    )
    environment = models.CharField(
        max_length=25,
        choices=ENVIRONMENT_CHOICES,
        default="development",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    environment_instance = models.ForeignKey(
        "core.EnvironmentInstance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etl_pipeline_versions",
    )
    dag_definition = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full declarative JSON snapshot of pipeline configuration and transformation steps",
    )
    changelog = models.TextField(
        blank=True,
        help_text="Release notes, schema changes, and transformation modifications",
    )
    rollback_source = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rolled_back_versions",
        help_text="Prior version restored by this rollback",
    )
    promoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etl_promotions",
    )
    promoted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bi_etl_pipeline_version"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bpvr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="idx_bpvr_ten_created_desc"),
            models.Index(fields=["tenant", "pipeline", "environment"], name="idx_bpvr_ten_pipe_env"),
            models.Index(fields=["tenant", "status"], name="idx_bpvr_ten_stat"),
        ]

    def __str__(self):
        return f"{self.number} ({self.version_number} [{self.get_environment_display()}])"
