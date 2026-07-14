"""CRM 1.6 Analytics & Reporting — Snapshots models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class ReportSnapshot(models.Model):
    """A point-in-time saved run of an ``AnalyticsReport`` (1.6) — freezes the computed result so
    a report can be compared period-over-period without re-querying historical state. Created
    only by the ``report_snapshot`` POST action, never by a user form. ``summary`` is the KPI
    card list, ``data`` is the full {columns, rows, chart_*} payload (rendered as-is, no recompute)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    report = models.ForeignKey("AnalyticsReport", on_delete=models.CASCADE, related_name="snapshots")
    title = models.CharField(max_length=160)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_report_snapshots")
    generated_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(default=list, blank=True)   # [{label, value}, ...] KPI cards
    data = models.JSONField(default=dict, blank=True)      # {columns, rows, chart_type, chart_labels, chart_data}

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["tenant", "report"], name="crm_snap_tnt_report_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.generated_at:%Y-%m-%d %H:%M})"
