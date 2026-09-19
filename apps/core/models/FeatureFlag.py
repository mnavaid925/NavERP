"""core — 0.10 bullet 2: Feature Flags & Toggles.

Bullet 2 names three scopes — per plan, per tenant, or per user group — and all three are here:
the ROW is the per-tenant toggle, `applies_to_plan` narrows it to a plan, and `exempt_roles` narrows
it to a set of roles. `is_feature_enabled()` resolves them in that order.

Deliberately NOT a `settings.py` flag and NOT a `LIVE_LINKS` entry. `LIVE_LINKS` answers "is this
sub-module built" and is a source of truth for the sidebar; a feature flag answers "should this
workspace see it", which is a different question that changes at runtime.
"""
from apps.core.models._base import *  # noqa: F401,F403


class FeatureFlag(models.Model):
    """One toggle for one tenant."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="feature_flags", db_index=True)
    key = models.CharField(max_length=120, help_text="Stable identifier, e.g. 'projects.gantt'.")
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    #: Blank means "all plans". Set it and the flag only applies to that plan, so a feature can be
    #: offered on `pro` without a second row per plan.
    applies_to_plan = models.CharField(max_length=20, blank=True)
    #: When non-empty, ONLY these roles see the feature. Empty means everyone in the workspace.
    exempt_roles = models.ManyToManyField("accounts.Role", blank=True, related_name="feature_flags")
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
        unique_together = ("tenant", "key")
        indexes = [models.Index(fields=["tenant", "key"], name="flag_tenant_key_idx")]

    def __str__(self):
        return f"{self.key} ({'on' if self.is_enabled else 'off'})"
