from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiNotificationItem(TenantNumbered):
    NUMBER_PREFIX = "BNTF"

    SEVERITY_CHOICES = [
        ("info", "Informational"),
        ("warning", "Warning"),
        ("critical", "Critical / Urgent"),
    ]

    CATEGORY_CHOICES = [
        ("kpi_alert", "KPI Threshold Alert"),
        ("anomaly_alert", "Statistical Anomaly Alert"),
        ("subscription_digest", "Report Subscription Delivery"),
        ("workflow_task", "Triggered Workflow Task"),
        ("system_bulletin", "System & Lineage Bulletin"),
    ]

    STATUS_CHOICES = [
        ("unread", "Unread"),
        ("read", "Read"),
        ("acknowledged", "Acknowledged"),
        ("snoozed", "Snoozed"),
        ("escalated", "Escalated"),
        ("dismissed", "Dismissed"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bi_notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default="info",
    )
    category = models.CharField(
        max_length=24,
        choices=CATEGORY_CHOICES,
        default="kpi_alert",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="unread",
    )
    alert_rule = models.ForeignKey(
        "bi.BiAlertRule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    burst_run = models.ForeignKey(
        "bi.DistributionBurstRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    action_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Deep link to relevant dashboard, report, or scorecard",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    acknowledgment_notes = models.TextField(blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    escalation_level = models.PositiveIntegerField(
        default=0,
        help_text="0=None, 1=Level 1 Manager, 2=Executive Escalation",
    )
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="escalated_bi_notifications",
    )
    workflow_converted = models.BooleanField(default=False)
    workflow_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="External Task ID or Approval Reference number",
    )

    class Meta:
        db_table = "bi_notification_item"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bntf_tenant_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "recipient", "status"], name="idx_bntf_ten_rec_stat"),
            models.Index(fields=["tenant", "severity"], name="idx_bntf_ten_sev"),
            models.Index(fields=["tenant", "category"], name="idx_bntf_ten_cat"),
            models.Index(fields=["tenant", "created_at"], name="idx_bntf_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    def get_absolute_url(self):
        return reverse("bi:bi_notification_item_detail", kwargs={"pk": self.pk})

    @property
    def severity_badge_class(self):
        mapping = {
            "critical": "badge-red",
            "warning": "badge-amber",
            "info": "badge-info",
        }
        return mapping.get(self.severity, "badge-slate")

    @property
    def status_badge_class(self):
        mapping = {
            "unread": "badge-info",
            "read": "badge-slate",
            "acknowledged": "badge-green",
            "snoozed": "badge-amber",
            "escalated": "badge-red",
            "dismissed": "badge-muted",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def category_badge_class(self):
        mapping = {
            "kpi_alert": "badge-amber",
            "anomaly_alert": "badge-slate",
            "subscription_digest": "badge-info",
            "workflow_task": "badge-green",
            "system_bulletin": "badge-slate",
        }
        return mapping.get(self.category, "badge-slate")
