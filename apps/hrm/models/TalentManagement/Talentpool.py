"""HRM 3.38 Talent Management & Succession — Talentpool models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TalentPool(TenantOwned):
    """A named talent segment (high-potentials, successor bench, critical-skill group, …). Small
    per-tenant catalog identified by name — not auto-numbered. Members join via TalentPoolMembership."""

    POOL_TYPE_CHOICES = [
        ("hipo", "High Potential"),
        ("successor", "Successor Bench"),
        ("critical_skill", "Critical Skill"),
        ("leadership", "Leadership Pipeline"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=150)
    pool_type = models.CharField(max_length=20, choices=POOL_TYPE_CHOICES, default="hipo")
    description = models.TextField(blank=True)
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="owned_talent_pools")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pool_type", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_tpool_tnt_active_idx"),
            models.Index(fields=["tenant", "pool_type"], name="hrm_tpool_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_pool_type_display()})"

    @property
    def active_member_count(self):
        """Uses the ``_active_member_count`` queryset annotation when the caller supplied one (the list
        view does, to avoid a per-row COUNT); falls back to a query for a lone instance."""
        annotated = getattr(self, "_active_member_count", None)
        if annotated is not None:
            return annotated
        return self.memberships.filter(status="active").count()
