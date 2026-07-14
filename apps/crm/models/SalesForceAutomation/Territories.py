"""CRM 1.2 Sales Force Automation — Territories models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ============================================================================
# ===== 1.2 Sales Force Automation (recreated) ===============================
# Opportunity splits, the sales Product catalog + price books, the Quote builder,
# territories, and sales quotas (the forecast/Kanban are views, not tables).
# ============================================================================
class Territory(TenantNumbered):
    """A sales territory (1.2 Forecasting) — region/segment with an optional parent for
    roll-up hierarchies; opportunities + quotas hang off it for forecast-by-territory."""

    NUMBER_PREFIX = "TER"

    name = models.CharField(max_length=255)
    region = models.CharField(max_length=120, blank=True)
    segment = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_territories")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_territories")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_ter_tnt_active_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_ter_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"
