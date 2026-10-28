"""Sales 8.18 — SalesSyncRun model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

RUN_TYPE_CHOICES = [
    ("manual", "Manual On-Demand"),
    ("scheduled", "Scheduled Batch"),
    ("webhook", "Inbound Webhook"),
    ("test_ping", "Health Ping / Test"),
]

STATUS_CHOICES = [
    ("simulated", "Simulated (Honest Diagnostic)"),
    ("completed", "Completed Successfully"),
    ("partial", "Completed with Warnings"),
    ("failed", "Execution Failed"),
]


class SalesSyncRun(TenantNumbered):
    NUMBER_PREFIX = "SSR"

    connector = models.ForeignKey(
        "sales.SalesIntegrationConnector",
        on_delete=models.CASCADE,
        related_name="sync_runs",
    )
    job = models.ForeignKey(
        "sales.SalesSyncJob",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sync_runs",
    )
    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES, default="manual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="simulated")
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_read = models.PositiveIntegerField(default=0)
    records_written = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True, default="")
    summary_payload = models.JSONField(default=dict, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_sync_runs",
    )

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_ssr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "connector", "status"], name="sales_ssr_conn_stat_idx"),
            models.Index(fields=["tenant", "job", "-started_at"], name="sales_ssr_job_start_idx"),
            models.Index(fields=["tenant", "-started_at"], name="sales_ssr_tenant_start_idx"),
        ]

    def clean(self):
        super().clean()
        if self.connector_id and self.tenant_id and self.connector.tenant_id != self.tenant_id:
            raise ValidationError({"connector": "Connector belongs to another tenant workspace."})
        if self.job_id and self.tenant_id and self.job.tenant_id != self.tenant_id:
            raise ValidationError({"job": "Sync job belongs to another tenant workspace."})

    def __str__(self):
        return f"{self.number} — {self.get_run_type_display()} ({self.get_status_display()})"
