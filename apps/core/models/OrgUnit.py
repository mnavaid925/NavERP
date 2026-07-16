"""core — OrgUnit models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class OrgUnit(models.Model):
    """Company / branch / department / team / cost-center hierarchy."""

    KIND_CHOICES = [
        ("company", "Company"),
        ("branch", "Branch"),
        ("department", "Department"),
        ("team", "Team"),
        ("cost_center", "Cost Center"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="org_units", db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="department")
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
