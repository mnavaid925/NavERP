"""HRM 3.20 Continuous Feedback — Kudosbadge models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.20 Continuous Feedback — the ongoing/informal performance layer: real-time
# kudos/appreciation/constructive feedback (incl. a request-feedback pull
# workflow + anonymous masking), 1:1 meetings with shared/private notes +
# action items, and a computed given/received/requested feedback dashboard
# (a view, NOT a 5th model — mirrors Objective.progress_pct). Third
# Performance-Management sub-module after 3.18 Goal Setting and 3.19 Performance
# Review; PIP/warning-letters/coaching are 3.21. Reuses the unified spine +
# already-built HRM models (NavERP-ERD.md): every person is an
# ``EmployeeProfile`` (giver/receiver, 1:1 manager/employee, action-item owner);
# feedback and 1:1s optionally link to a 3.18 ``Objective`` or a 3.19
# ``PerformanceReview`` for work context. Adds ONLY the Feedback/1:1 tables + a
# small KudosBadge catalog — no new core-spine entity, posts no GL. Confidentiality
# clones 3.19 field-for-field: ``OneOnOneMeeting.manager_private_notes`` clones
# ``PerformanceReview.private_notes`` (manager-only, never rendered employee-side)
# and ``Feedback.is_anonymous`` clones the reviewer-masking pattern (giver hidden
# from non-admins on read).
# ---------------------------------------------------------------------------
class KudosBadge(TenantOwned):
    """A small per-tenant recognition-badge catalog — the values/company-value tags a kudos can
    carry ("Team Player", "Above & Beyond", …). Same shape as ``JobGrade``/``GoalPeriod``/
    ``ReviewCycle``: identified by ``name``, not auto-numbered."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon name for the UI chip.")
    color = models.CharField(max_length=20, blank=True, help_text="Hex or Tailwind class for the chip.")
    linked_value = models.CharField(max_length=100, blank=True,
                                    help_text="Free-text company value this badge celebrates (e.g. 'Customer First').")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_kb_tenant_active_idx"),
        ]

    @property
    def usage_count(self):
        return self.feedback_items.count()

    def __str__(self):
        return self.name
