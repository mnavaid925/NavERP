"""HRM 3.32 Analytics Dashboard — Dashboard models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


DASHBOARD_LAYOUT_CHOICES = [("one", "Single column"), ("two", "Two columns"), ("three", "Three columns")]


class HRDashboard(TenantNumbered):
    """A saved, per-user HR analytics dashboard (3.32). Holds HRDashboardWidget tiles computed
    live on render. ``is_shared`` exposes it to the whole tenant; ``is_default`` marks the owner's
    landing dashboard. Mirrors ``crm.AnalyticsDashboard``."""

    NUMBER_PREFIX = "HRD"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="hrm_dashboards")
    is_shared = models.BooleanField(default=False)   # visible to the whole tenant, not just the owner
    is_default = models.BooleanField(default=False)  # the owner's landing dashboard
    layout = models.CharField(max_length=10, choices=DASHBOARD_LAYOUT_CHOICES, default="two")

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "owner"], name="hrm_hrdash_tnt_owner_idx"),
            models.Index(fields=["tenant", "is_shared"], name="hrm_hrdash_tnt_shared_idx"),
        ]

    @property
    def widget_count(self):
        return self.widgets.count()

    def __str__(self):
        return f"{self.number} · {self.name}"
