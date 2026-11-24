from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class AuditReportDefinition(TenantNumbered):
    """Configurable and system-preset audit and compliance report queries."""

    NUMBER_PREFIX = "DRPT"

    REPORT_TYPE_CHOICES = (
        ("document_history", "Complete Document Lifecycle History"),
        ("user_activity", "User Access & Activity Summary"),
        ("confidential_access", "Confidential / Restricted Document Access"),
        ("permission_audit", "Permission & Access Control Changes"),
        ("security_exceptions", "Security Exceptions & DLP Blocks"),
        ("external_sharing", "External Sharing & Public Links"),
        ("deletion_purge", "Document Deletions & Purges"),
        ("lifecycle_bottlenecks", "Approval Cycle Time & Bottlenecks"),
        ("version_churn", "Version Volatility & High Churn"),
        ("custom_query", "Custom Filtered Audit Query"),
    )

    DATE_RANGE_CHOICES = (
        ("today", "Today"),
        ("last_7_days", "Last 7 Days"),
        ("last_30_days", "Last 30 Days"),
        ("last_90_days", "Last 90 Days"),
        ("last_year", "Last 365 Days"),
        ("custom", "Custom Date Range"),
    )

    OUTPUT_FORMAT_CHOICES = (
        ("table_view", "Interactive Web Table"),
        ("csv", "Downloadable CSV"),
        ("json", "Downloadable JSON"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("archived", "Archived"),
    )

    REPORT_TYPE_CSS = {
        "document_history": "badge-info",
        "user_activity": "badge-slate",
        "confidential_access": "badge-amber",
        "permission_audit": "badge-info",
        "security_exceptions": "badge-red",
        "external_sharing": "badge-amber",
        "deletion_purge": "badge-red",
        "lifecycle_bottlenecks": "badge-amber",
        "version_churn": "badge-slate",
        "custom_query": "badge-green",
    }

    STATUS_CSS = {
        "active": "badge-green",
        "archived": "badge-muted",
    }

    name = models.CharField(
        max_length=150,
        help_text="Human-readable title of report definition",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed purpose and regulatory scope of this audit report",
    )
    report_type = models.CharField(
        max_length=40,
        choices=REPORT_TYPE_CHOICES,
        default="custom_query",
        db_index=True,
    )
    is_system_preset = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this is a built-in preconfigured compliance report",
    )
    date_range_preset = models.CharField(
        max_length=30,
        choices=DATE_RANGE_CHOICES,
        default="last_30_days",
    )
    custom_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Used when date_range_preset is 'custom'",
    )
    custom_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Used when date_range_preset is 'custom'",
    )
    filter_criteria_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dynamic criteria e.g. action_types, user_ids, folder_ids, min_risk",
    )
    output_format = models.CharField(
        max_length=20,
        choices=OUTPUT_FORMAT_CHOICES,
        default="table_view",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_created_audit_reports",
    )
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of most recent execution",
    )
    last_run_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_executed_audit_reports",
    )
    total_runs = models.PositiveIntegerField(
        default=0,
        help_text="Execution counter",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Audit Report Definition"
        verbose_name_plural = "Audit Report Definitions"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_drpt_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "report_type"], name="doc_drpt_tnt_typ_idx"),
            models.Index(fields=["tenant", "status"], name="doc_drpt_tnt_sts_idx"),
            models.Index(fields=["tenant", "is_system_preset"], name="doc_drpt_tnt_sys_idx"),
        ]

    def __str__(self):
        preset_tag = " [Preset]" if self.is_system_preset else ""
        return f"{self.name} ({self.number}){preset_tag}"

    def get_report_type_badge(self):
        return self.REPORT_TYPE_CSS.get(self.report_type, "badge-slate")

    def get_status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def get_effective_date_range(self):
        """Returns (start_datetime, end_datetime) tuple based on preset or custom dates."""
        now = timezone.now()
        preset = self.date_range_preset

        if preset == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        elif preset == "last_7_days":
            return now - timedelta(days=7), now
        elif preset == "last_30_days":
            return now - timedelta(days=30), now
        elif preset == "last_90_days":
            return now - timedelta(days=90), now
        elif preset == "last_year":
            return now - timedelta(days=365), now
        elif preset == "custom":
            start = timezone.make_aware(
                timezone.datetime.combine(self.custom_start_date, timezone.datetime.min.time())
            ) if self.custom_start_date else (now - timedelta(days=30))
            end = timezone.make_aware(
                timezone.datetime.combine(self.custom_end_date, timezone.datetime.max.time())
            ) if self.custom_end_date else now
            return start, end

        return now - timedelta(days=30), now

    def execute_query(self, user=None):
        """Execute audit trail query matching this definition and compute summary KPI metrics."""
        from django.db.models import Count, Q
        from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail

        start_dt, end_dt = self.get_effective_date_range()
        events_qs = DocumentAuditTrail.objects.filter(
            tenant=self.tenant,
            event_timestamp__range=(start_dt, end_dt),
        ).select_related("document", "actor", "version")

        rtype = self.report_type
        if rtype == "confidential_access":
            events_qs = events_qs.filter(action_type__in=["viewed", "previewed", "downloaded", "printed"])
        elif rtype == "permission_audit":
            events_qs = events_qs.filter(action_type="permission_changed")
        elif rtype == "security_exceptions":
            events_qs = events_qs.filter(Q(is_success=False) | Q(action_type="dlp_violation"))
        elif rtype == "external_sharing":
            events_qs = events_qs.filter(action_type__in=["shared_externally", "share_revoked"])
        elif rtype == "deletion_purge":
            events_qs = events_qs.filter(action_type__in=["deleted", "purged"])
        elif rtype == "lifecycle_bottlenecks":
            events_qs = events_qs.filter(action_type__in=["workflow_approved", "workflow_rejected"])
        elif rtype == "version_churn":
            events_qs = events_qs.filter(action_type="version_uploaded")

        agg = events_qs.aggregate(
            total_events=Count("id"),
            failed_events=Count("id", filter=Q(is_success=False)),
            unique_actors=Count("actor", distinct=True),
        )
        total_events = agg["total_events"] or 0
        failed_events = agg["failed_events"] or 0
        success_events = total_events - failed_events
        success_rate = round((success_events / total_events * 100), 1) if total_events > 0 else 100.0
        unique_actors = agg["unique_actors"] or 0

        summary_kpis = {
            "total_events": total_events,
            "success_events": success_events,
            "failed_events": failed_events,
            "success_rate": success_rate,
            "unique_actors": unique_actors,
        }

        self.last_run_at = timezone.now()
        if user:
            self.last_run_by = user
        self.total_runs += 1
        if self.pk:
            self.save(update_fields=["last_run_at", "last_run_by", "total_runs"] if user else ["last_run_at", "total_runs"])

        return events_qs, summary_kpis

