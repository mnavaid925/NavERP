"""CRM 1.6 Analytics & Reporting — Dashboards models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.AnalyticsReporting._choices import DASHBOARD_LAYOUT_CHOICES


class AnalyticsDashboard(TenantNumbered):
    """A saved, per-user CRM dashboard (1.6). Holds a set of ``DashboardWidget`` tiles that are
    computed live on render (real-time data). ``is_shared`` exposes it to the whole tenant;
    ``is_default`` marks the one opened first. The owner can keep private dashboards."""

    NUMBER_PREFIX = "DASH"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_dashboards")
    is_shared = models.BooleanField(default=False)  # visible to the whole tenant, not just the owner
    is_default = models.BooleanField(default=False)  # the landing dashboard
    layout = models.CharField(max_length=10, choices=DASHBOARD_LAYOUT_CHOICES, default="two")

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "owner"], name="crm_dash_tnt_owner_idx"),
            models.Index(fields=["tenant", "is_shared"], name="crm_dash_tnt_shared_idx"),
        ]

    @property
    def widget_count(self):
        return self.widgets.count()

    def __str__(self):
        return f"{self.number} · {self.name}"
