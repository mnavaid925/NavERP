"""CRM 1.4 Customer Service & Support — SlaPolicies models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ============================================================================
# ===== 1.4 Customer Service & Support / Help Desk (recreated) ================
# SLA policies + the case conversation thread, KB categories, and the customer
# self-service portal access (the portal + public pages are views, not tables).
# ============================================================================
class SlaPolicy(TenantNumbered):
    """A service-level policy (1.4) — per-priority first-response + resolution targets in HOURS.

    One named policy covers all four priorities; a Case picks a policy and ``save()`` computes its
    due timestamps from ``targets_for(priority)``. (Business-hours calendars are deferred.)"""

    NUMBER_PREFIX = "SLA"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    # First-response targets (hours) per priority.
    response_low = models.PositiveSmallIntegerField(default=48)
    response_medium = models.PositiveSmallIntegerField(default=24)
    response_high = models.PositiveSmallIntegerField(default=8)
    response_critical = models.PositiveSmallIntegerField(default=2)
    # Resolution targets (hours) per priority.
    resolution_low = models.PositiveSmallIntegerField(default=240)
    resolution_medium = models.PositiveSmallIntegerField(default=120)
    resolution_high = models.PositiveSmallIntegerField(default=48)
    resolution_critical = models.PositiveSmallIntegerField(default=8)

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_sla_tnt_active_idx"),
            models.Index(fields=["tenant", "is_default"], name="crm_sla_tnt_default_idx"),
        ]

    def targets_for(self, priority):
        """Return ``(first_response_hours, resolution_hours)`` for a Case priority."""
        return (
            getattr(self, f"response_{priority}", None),
            getattr(self, f"resolution_{priority}", None),
        )

    def __str__(self):
        return f"{self.number} · {self.name}"
