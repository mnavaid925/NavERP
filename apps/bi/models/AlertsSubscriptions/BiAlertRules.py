from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiAlertRule(TenantNumbered):
    NUMBER_PREFIX = "BALR"

    ALERT_TYPE_CHOICES = [
        ("kpi_threshold", "KPI Metric Threshold"),
        ("anomaly_detection", "Statistical Anomaly Trigger"),
        ("query_threshold", "Ad-Hoc Query Result Count"),
        ("trend_variance", "Trend & Percentage Variance"),
    ]

    CONDITION_OPERATOR_CHOICES = [
        ("gt", "Greater Than (>)"),
        ("gte", "Greater Than or Equal (>=)"),
        ("lt", "Less Than (<)"),
        ("lte", "Less Than or Equal (<=)"),
        ("eq", "Equals (==)"),
        ("outside_range", "Outside Target Range"),
        ("pct_change_gt", "Percentage Increase Exceeds (%)"),
        ("pct_change_lt", "Percentage Drop Exceeds (%)"),
        ("anomaly_flagged", "Anomaly Outlier Flagged"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Informational"),
        ("warning", "Warning"),
        ("critical", "Critical / Urgent"),
    ]

    EVALUATION_CADENCE_CHOICES = [
        ("on_data_refresh", "On Ingestion / Pipeline Refresh"),
        ("every_15_mins", "Every 15 Minutes"),
        ("hourly", "Hourly"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]

    TRIGGER_FREQUENCY_CHOICES = [
        ("every_time", "Send Notification Every Time Breach Occurs"),
        ("once_until_resolved", "Send Once Until Condition Clears"),
        ("one_off", "Single Disposable Trigger Then Disable"),
    ]

    DELIVERY_CHANNEL_CHOICES = [
        ("in_app_only", "In-App Notification Center Only"),
        ("in_app_email", "In-App and Email Digest"),
        ("slack_webhook", "Slack / Microsoft Teams Webhook"),
        ("multi_channel", "All Channels (In-App, Email, Webhook)"),
    ]

    DOWNSTREAM_WORKFLOW_CHOICES = [
        ("none", "No Automated Workflow"),
        ("create_task", "Create Follow-Up Project Task"),
        ("request_approval", "Submit Incident Approval Request"),
        ("trigger_webhook", "Dispatch Downstream Automation Webhook"),
    ]

    STATUS_CHOICES = [
        ("active", "Active & Monitoring"),
        ("paused", "Paused / Inactive"),
        ("tripped", "Tripped / In Breach State"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    alert_type = models.CharField(
        max_length=24,
        choices=ALERT_TYPE_CHOICES,
        default="kpi_threshold",
    )
    kpi_definition = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alert_rules",
    )
    anomaly_detection = models.ForeignKey(
        "bi.StatisticalAnomaly",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alert_rules",
    )
    condition_operator = models.CharField(
        max_length=24,
        choices=CONDITION_OPERATOR_CHOICES,
        default="gt",
    )
    threshold_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Target threshold or comparison baseline value",
    )
    secondary_threshold_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Upper boundary for outside_range condition",
    )
    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default="warning",
    )
    evaluation_cadence = models.CharField(
        max_length=20,
        choices=EVALUATION_CADENCE_CHOICES,
        default="hourly",
    )
    trigger_frequency = models.CharField(
        max_length=24,
        choices=TRIGGER_FREQUENCY_CHOICES,
        default="once_until_resolved",
    )
    delivery_channel = models.CharField(
        max_length=20,
        choices=DELIVERY_CHANNEL_CHOICES,
        default="in_app_email",
    )
    recipient_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="bi_alert_subscriptions",
    )
    notification_email_list = models.TextField(
        blank=True,
        help_text="Comma-separated external subscriber email addresses",
    )
    webhook_url = models.URLField(
        blank=True,
        help_text="Slack/Teams or external automation webhook endpoint",
    )
    downstream_workflow = models.CharField(
        max_length=24,
        choices=DOWNSTREAM_WORKFLOW_CHOICES,
        default="none",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="active",
    )
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    last_trigger_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_bi_alerts",
    )

    class Meta:
        db_table = "bi_alert_rule"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_balr_tenant_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "alert_type"], name="idx_balr_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_balr_ten_status"),
            models.Index(fields=["tenant", "severity"], name="idx_balr_ten_sev"),
            models.Index(fields=["tenant", "last_evaluated_at"], name="idx_balr_ten_eval"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    def get_absolute_url(self):
        return reverse("bi:bi_alert_rule_detail", kwargs={"pk": self.pk})

    @property
    def severity_badge_class(self):
        mapping = {
            "critical": "badge-red",
            "warning": "badge-amber",
            "info": "badge-blue",
        }
        return mapping.get(self.severity, "badge-slate")

    @property
    def status_badge_class(self):
        mapping = {
            "active": "badge-green",
            "tripped": "badge-red",
            "paused": "badge-amber",
            "archived": "badge-slate",
        }
        return mapping.get(self.status, "badge-slate")
