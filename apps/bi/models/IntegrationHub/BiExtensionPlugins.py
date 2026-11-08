from django.conf import settings
from django.db import models

from apps.bi.models._base import TenantNumbered


class BiExtensionPlugin(TenantNumbered):
    NUMBER_PREFIX = "BEXT"

    PLUGIN_TYPE_CHOICES = [
        ("custom_visual", "Custom Visualization Canvas Component"),
        ("connector_plugin", "Third-Party Data Connector Plug-in"),
        ("transformation_script", "Custom ETL Transformation Step"),
        ("dashboard_extension", "Interactive Dashboard Extension Action"),
        ("metric_provider", "External Metric & Benchmark Provider"),
    ]

    CATEGORY_CHOICES = [
        ("visualization", "Charts & Visual Displays"),
        ("data_integration", "Ingestion & Reverse ETL"),
        ("governance", "Data Governance & Quality"),
        ("advanced_analytics", "Predictive & Statistical Tools"),
        ("workflow_action", "Operational Closed-Loop Actions"),
    ]

    STATUS_CHOICES = [
        ("installed", "Installed (Not Enabled)"),
        ("enabled", "Enabled & Active"),
        ("disabled", "Disabled by Administrator"),
        ("deprecated", "Deprecated Version"),
        ("quarantined", "Quarantined (Security Flagged)"),
    ]

    name = models.CharField(max_length=200)
    plugin_identifier = models.CharField(
        max_length=120,
        help_text="Reverse-DNS unique package identifier (e.g. io.naverp.visuals.sankey)",
    )
    version = models.CharField(max_length=30, default="1.0.0")

    plugin_type = models.CharField(
        max_length=40,
        choices=PLUGIN_TYPE_CHOICES,
        default="custom_visual",
    )
    category = models.CharField(
        max_length=40,
        choices=CATEGORY_CHOICES,
        default="visualization",
    )
    description = models.TextField(blank=True)
    author_name = models.CharField(max_length=150)
    homepage_url = models.URLField(max_length=500, blank=True)
    repository_url = models.URLField(max_length=500, blank=True)
    license = models.CharField(max_length=60, default="MIT")

    manifest_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Package manifest (entrypoint JS, CSS, icon SVG, min_naverp_version)",
    )
    config_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON Schema definition for customizable settings",
    )
    current_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Active tenant-specific configuration values",
    )
    permissions_required = models.JSONField(
        default=list,
        blank=True,
        help_text="Declared sandboxed permissions (e.g. read_semantic_layer, network_egress)",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="installed",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Verification badge from NavERP Data Governance",
    )
    is_system_plugin = models.BooleanField(
        default=False,
        help_text="Protected system-bundled extension",
    )

    installed_at = models.DateTimeField(auto_now_add=True)
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_installed_plugins",
    )

    class Meta:
        db_table = "bi_extension_plugin"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bext_ten_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "plugin_identifier"],
                name="bi_bext_ten_ident_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_bext_ten_stat"),
            models.Index(fields=["tenant", "plugin_type"], name="idx_bext_ten_type"),
            models.Index(fields=["tenant", "category"], name="idx_bext_ten_cat"),
            models.Index(fields=["tenant", "is_verified"], name="idx_bext_ten_ver"),
            models.Index(fields=["tenant", "created_at"], name="idx_bext_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} v{self.version} ({self.plugin_identifier})"
