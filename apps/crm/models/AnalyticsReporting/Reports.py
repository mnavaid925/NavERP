"""CRM 1.6 Analytics & Reporting — Reports models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.AnalyticsReporting._choices import ANALYTICS_RANGE_CHOICES, REPORT_GROUP_CHOICES, REPORT_TYPE_CHOICES


class AnalyticsReport(TenantNumbered):
    """A saved standard report (1.6) — one of four canned report types computed live over the
    CRM data (see ``analytics.compute_report``). ``last_run_at`` is system-stamped whenever the
    report is rendered or snapshotted (never on the form). ``is_favorite`` pins it to the top."""

    NUMBER_PREFIX = "RPT"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default="sales_activity")
    date_range = models.CharField(max_length=10, choices=ANALYTICS_RANGE_CHOICES, default="last_90")
    group_by = models.CharField(max_length=10, choices=REPORT_GROUP_CHOICES, default="month")
    is_favorite = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_reports")
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)  # system-set on render/snapshot

    class Meta:
        ordering = ["-is_favorite", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "report_type"], name="crm_rpt_tnt_type_idx"),
            models.Index(fields=["tenant", "is_favorite"], name="crm_rpt_tnt_fav_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
