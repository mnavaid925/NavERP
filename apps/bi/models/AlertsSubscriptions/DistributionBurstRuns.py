from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.bi.models._base import TenantNumbered


class DistributionBurstRun(TenantNumbered):
    NUMBER_PREFIX = "BBRS"

    RUN_TRIGGER_CHOICES = [
        ("scheduled_subscription", "Scheduled Subscription Batch"),
        ("ad_hoc_manual", "Manual Ad-Hoc Burst Dispatch"),
        ("alert_triggered", "Triggered from Tripped Alert Rule"),
    ]

    DELIVERY_CHANNEL_CHOICES = [
        ("email", "Email (SMTP)"),
        ("sftp", "Secure FTP Drop (SFTP)"),
        ("portal_inbox", "In-App Portal Inbox"),
        ("webhook", "External Webhook"),
    ]

    STATUS_CHOICES = [
        ("queued", "Queued for Generation"),
        ("processing", "Processing & Slicing Batches"),
        ("completed", "Completed Successfully"),
        ("partial_failure", "Partial Failure (Some Recipients Failed)"),
        ("failed", "Failed"),
    ]

    subscription = models.ForeignKey(
        "bi.ReportSubscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="burst_runs",
    )
    alert_rule = models.ForeignKey(
        "bi.BiAlertRule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="burst_runs",
    )
    run_trigger = models.CharField(
        max_length=24,
        choices=RUN_TRIGGER_CHOICES,
        default="scheduled_subscription",
    )
    delivery_channel = models.CharField(
        max_length=16,
        choices=DELIVERY_CHANNEL_CHOICES,
        default="email",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed",
    )
    recipient_count = models.PositiveIntegerField(default=1)
    delivered_count = models.PositiveIntegerField(default=1)
    failed_count = models.PositiveIntegerField(default=0)
    execution_duration_ms = models.IntegerField(default=0)
    generated_file_name = models.CharField(max_length=255, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    burst_slicing_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Details of per-recipient data partitions, filters, and deliver destinations",
    )
    error_summary = models.TextField(
        blank=True,
        help_text="Error trace or recipient failure diagnostics",
    )
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="executed_burst_runs",
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bi_distribution_burst_run"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bbrs_tenant_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "run_trigger"], name="idx_bbrs_ten_trig"),
            models.Index(fields=["tenant", "status"], name="idx_bbrs_ten_stat"),
            models.Index(fields=["tenant", "started_at"], name="idx_bbrs_ten_start"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("bi:distribution_burst_run_detail", kwargs={"pk": self.pk})

    @property
    def status_badge_class(self):
        mapping = {
            "completed": "badge-green",
            "processing": "badge-info",
            "queued": "badge-amber",
            "partial_failure": "badge-amber",
            "failed": "badge-red",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def channel_badge_class(self):
        mapping = {
            "email": "badge-info",
            "sftp": "badge-slate",
            "portal_inbox": "badge-green",
            "webhook": "badge-amber",
        }
        return mapping.get(self.delivery_channel, "badge-slate")
