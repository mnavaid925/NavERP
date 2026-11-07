import datetime

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class ReportSubscription(TenantNumbered):
    NUMBER_PREFIX = "BSUB"

    TARGET_ASSET_TYPE_CHOICES = [
        ("dashboard", "Executive Dashboard"),
        ("report", "Operational Report"),
    ]

    EXPORT_FORMAT_CHOICES = [
        ("pdf", "Portable Document Format (PDF)"),
        ("xlsx", "Microsoft Excel Spreadsheet (XLSX)"),
        ("csv", "Comma-Separated Values (CSV)"),
        ("html_inline", "Interactive HTML Inline Digest"),
    ]

    CADENCE_CHOICES = [
        ("daily", "Daily Morning Digest"),
        ("weekly", "Weekly Monday Summary"),
        ("monthly", "Monthly Financial Close Summary"),
        ("quarterly", "Quarterly Review"),
        ("cron", "Custom Cron Schedule"),
    ]

    BURST_MODE_CHOICES = [
        ("broadcast", "Standard Broadcast (Identical Content to All Recipients)"),
        ("slice_by_user", "Recipient-Personalized Data Bursting (Row-Level Access)"),
        ("slice_by_org_unit", "Department / OrgUnit Sliced Bursting"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Scheduled"),
        ("paused", "Paused Delivery"),
        ("failed", "Delivery Errored / Retrying"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    target_asset_type = models.CharField(
        max_length=16,
        choices=TARGET_ASSET_TYPE_CHOICES,
        default="dashboard",
    )
    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subscriptions",
    )
    report = models.ForeignKey(
        "bi.ReportDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subscriptions",
    )
    export_format = models.CharField(
        max_length=16,
        choices=EXPORT_FORMAT_CHOICES,
        default="pdf",
    )
    cadence = models.CharField(
        max_length=16,
        choices=CADENCE_CHOICES,
        default="weekly",
    )
    scheduled_time = models.TimeField(
        default=datetime.time(8, 0),
        help_text="Time of day for delivery",
    )
    cron_expression = models.CharField(
        max_length=64,
        blank=True,
        default="0 8 * * 1",
        help_text="Cron pattern if cadence is custom cron",
    )
    burst_mode = models.CharField(
        max_length=20,
        choices=BURST_MODE_CHOICES,
        default="broadcast",
    )
    subscriber_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="bi_report_subscriptions",
    )
    subscriber_org_units = models.ManyToManyField(
        "core.OrgUnit",
        blank=True,
        related_name="bi_report_subscriptions",
    )
    external_recipient_emails = models.TextField(
        blank=True,
        help_text="Comma-separated external recipient email addresses",
    )
    filter_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom dimensional filter values applied to generated artifact",
    )
    include_cover_page = models.BooleanField(
        default=True,
        help_text="Include branded summary header in generated document",
    )
    skip_if_empty = models.BooleanField(
        default=False,
        help_text="Suppress delivery if report returns zero rows",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="active",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_bi_subscriptions",
    )

    class Meta:
        db_table = "bi_report_subscription"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bsub_tenant_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "target_asset_type"], name="idx_bsub_ten_target"),
            models.Index(fields=["tenant", "cadence"], name="idx_bsub_ten_cadence"),
            models.Index(fields=["tenant", "status"], name="idx_bsub_ten_status"),
            models.Index(fields=["tenant", "next_run_at"], name="idx_bsub_ten_next"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    def get_absolute_url(self):
        return reverse("bi:report_subscription_detail", kwargs={"pk": self.pk})

    @property
    def status_badge_class(self):
        mapping = {
            "active": "badge-green",
            "paused": "badge-amber",
            "failed": "badge-red",
            "archived": "badge-slate",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def format_badge_class(self):
        mapping = {
            "pdf": "badge-red",
            "xlsx": "badge-green",
            "csv": "badge-info",
            "html_inline": "badge-slate",
        }
        return mapping.get(self.export_format, "badge-slate")
