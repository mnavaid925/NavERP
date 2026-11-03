from django.conf import settings
from django.db import models

from apps.bi.models._base import TenantNumbered


class DataSourceConnector(TenantNumbered):
    NUMBER_PREFIX = "BDSC"

    CONNECTOR_TYPE_CHOICES = [
        ("internal_erp", "NavERP Internal Module"),
        ("database_rdbms", "Relational Database (RDBMS)"),
        ("database_nosql", "NoSQL / Document Store"),
        ("cloud_storage", "Cloud Object Storage (S3/GCS/Azure)"),
        ("sftp_server", "SFTP / Secure File Server"),
        ("rest_api", "REST API Endpoint"),
        ("webhook_push", "Inbound HTTP Webhook"),
        ("file_upload", "Manual File Upload Buffer"),
    ]

    STATUS_CHOICES = [
        ("active", "Active / Ready"),
        ("inactive", "Inactive / Disabled"),
        ("testing", "Testing Connection"),
        ("error", "Connection Error"),
    ]

    TEST_STATUS_CHOICES = [
        ("untested", "Untested"),
        ("success", "Connection Verified"),
        ("failed", "Connection Failed"),
    ]

    name = models.CharField(max_length=150, help_text="Source connector identifier name")
    connector_type = models.CharField(
        max_length=30,
        choices=CONNECTOR_TYPE_CHOICES,
        default="internal_erp",
        help_text="Integration protocol and source category",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Operational readiness status",
    )
    connection_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Host, port, database, bucket, sftp_path, query_options",
    )
    credential = models.ForeignKey(
        "core.ApiCredential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_connectors",
        help_text="Optional verified API credential for authentication",
    )
    discovered_catalog = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cached list of discovered streams, tables, and column attributes",
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    test_status = models.CharField(
        max_length=20,
        choices=TEST_STATUS_CHOICES,
        default="untested",
    )
    test_message = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_connectors_created",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdsc_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "connector_type"], name="idx_bdsc_ten_stat_type"),
            models.Index(fields=["tenant", "name"], name="idx_bdsc_ten_name"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_connector_type_display()})"
