"""HRM 3.36 Helpdesk — Helpdeskslapolicy models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.36 Helpdesk — the employee HR/IT/Admin/Facilities service desk. Categories
# (routing taxonomy, doubling as the KB taxonomy) carry a default assignee + default
# SLA policy; SLA policies hold per-priority response/resolution hour targets
# (mirrors crm.SlaPolicy); tickets are agent-worked (assign/start/resolve/close/
# reopen/feedback — NOT the single-approver _hr_request_* machine) with SLA due
# timestamps stamped once in save() and breach/at-risk COMPUTED (mirrors crm.Case);
# post-resolution CSAT is captured inline (no separate survey model, like crm.Case).
# The requester FK is named ``employee`` so tickets reuse the self-service helpers
# (_ss_scope / _can_manage_own_child). KnowledgeArticle is an internal-only FAQ/
# self-help repository (no public portal token). Reuses the unified spine: requester
# = core.Party -> hrm.EmployeeProfile; assignee/owner = auth User; tenant-scoped.
# ---------------------------------------------------------------------------
class HelpdeskSLAPolicy(TenantNumbered):
    """Per-priority response/resolution hour targets (``HSLA-#####``) — a field-for-field mirror of
    ``crm.SlaPolicy``. A new ticket copies its category's ``default_sla_policy`` and ``save()`` stamps
    the ticket's due timestamps from ``targets_for(priority)``. Calendar-hours this pass (not
    business-hours clocks — deferred). The catalog row is editable; a ticket's stamped dues never move."""

    NUMBER_PREFIX = "HSLA"

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    urgent_response_hours = models.PositiveIntegerField(default=1)
    urgent_resolution_hours = models.PositiveIntegerField(default=4)
    high_response_hours = models.PositiveIntegerField(default=4)
    high_resolution_hours = models.PositiveIntegerField(default=24)
    medium_response_hours = models.PositiveIntegerField(default=8)
    medium_resolution_hours = models.PositiveIntegerField(default=48)
    low_response_hours = models.PositiveIntegerField(default=24)
    low_resolution_hours = models.PositiveIntegerField(default=96)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_hsla_tnt_active_idx"),
            models.Index(fields=["tenant", "is_default"], name="hrm_hsla_tnt_default_idx"),
        ]

    def __str__(self):
        return self.name

    def targets_for(self, priority):
        """``(response_hours, resolution_hours)`` for a ``HelpdeskTicket`` priority (medium fallback)."""
        return {
            "urgent": (self.urgent_response_hours, self.urgent_resolution_hours),
            "high": (self.high_response_hours, self.high_resolution_hours),
            "medium": (self.medium_response_hours, self.medium_resolution_hours),
            "low": (self.low_response_hours, self.low_resolution_hours),
        }.get(priority, (self.medium_response_hours, self.medium_resolution_hours))
