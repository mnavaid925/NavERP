"""HRM 3.2 Organizational Structure — Jobgrade models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.2 Organizational Structure — JobGrade + Designation + Department/CostCenter
# companions to ``core.OrgUnit``. Departments and cost-centers are canonical
# ``core.OrgUnit`` nodes (name/parent/hierarchy live there); HRM never duplicates
# them — it adds a thin tenant-scoped companion table (head/owner/budget/code) that
# core cannot hold, mirroring how ``EmployeeProfile`` extends ``core.Party``. The org
# chart is DERIVED from ``core.Employment.manager`` + ``OrgUnit.parent`` (a view, no model).
# ---------------------------------------------------------------------------
class JobGrade(TenantOwned):
    """Orderable job-grade / level catalog (3.2). ``level_order`` ranks seniority (1 = most
    junior) for hierarchy display and org-chart level-coloring. Replaces the free-text
    ``Designation.grade`` CharField as the primary grade reference (the CharField is kept for
    back-compat). Small per-tenant catalog identified by name — not auto-numbered."""

    name = models.CharField(max_length=50)
    level_order = models.PositiveSmallIntegerField(default=1)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level_order", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_jg_tenant_active_idx"),
            models.Index(fields=["tenant", "level_order"], name="hrm_jg_tenant_order_idx"),
        ]

    def __str__(self):
        return f"{self.name} (L{self.level_order})" if self.level_order else self.name
