"""HRM 3.3 Employee Onboarding — Template models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class OnboardingTemplate(TenantNumbered):
    """A reusable onboarding checklist (3.3) — applied to a new hire to spin up a program.
    Optionally tied to a ``Designation`` so HR can auto-suggest the right template per role."""

    NUMBER_PREFIX = "ONBT"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="onboarding_templates")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("tenant", "number"), ("tenant", "name")]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_onbt_tenant_active_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_onbt_tenant_desig_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name
