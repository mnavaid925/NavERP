"""Projects 7.5 — IssueEscalation [ESC-]: one record of an issue pushed up the chain of command.

Bullet **4 Issue Logging & Escalation** owns this row. A ``ProjectIssue`` is the problem; an
escalation is the act of telling someone above you about it — who was told (``target_role`` /
``target_user``), why (``reason``) and what came of it (``outcome``). The issue detail page renders
its own escalation path straight from these rows, so the register and the issue can never disagree
about how far an issue travelled.

**No verbs of its own.** ``IssueEscalation`` has no status and no lifecycle: rows are appended by
``iss_escalate`` (which also bumps ``ProjectIssue.escalation_level``) and by this register's own
create. ``escalated_at`` is stamped on insert (``auto_now_add``) and ``escalated_by`` /
``created_by`` are written by the view, so the trail keeps its timestamps.

**Boundary (L36):** ``issue`` is FK'd **by string** into the 7.5 issue log — the issue model is not
re-declared here. ``LEVEL_CHOICES`` is a documented class constant (the same idiom as the risk
register's band maps): the four escalation tiers are a fixed vocabulary, and the register filter and
the form both read it, so there is exactly one definition of "level 3".
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class IssueEscalation(TenantNumbered):
    NUMBER_PREFIX = "ESC"

    #: The four escalation tiers. A documented class constant, not a per-tenant table: the filter,
    #: the form and ``iss_escalate`` all read this one list.
    LEVEL_CHOICES = [
        (1, "Level 1 — Team Lead"),
        (2, "Level 2 — Project Manager"),
        (3, "Level 3 — Program Manager"),
        (4, "Level 4 — Executive Sponsor"),
    ]

    issue = models.ForeignKey(
        "projects.ProjectIssue", on_delete=models.CASCADE, related_name="escalations")
    level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="1 (team lead) … 4 (executive sponsor).")
    #: The role told, recorded as text so the trail survives a later org change.
    target_role = models.CharField(max_length=80, blank=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="issue_escalations")
    #: Why the issue was pushed up — required: an escalation with no reason is not a record.
    reason = models.TextField()
    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="escalations_raised")
    escalated_at = models.DateTimeField(auto_now_add=True)
    #: The outcome capture — filled in as the escalation is answered, not on the way up.
    resolved_at = models.DateTimeField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="esc_created")

    class Meta:
        ordering = ["issue_id", "level", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "issue"], name="esc_tnt_issue_idx"),
            models.Index(fields=["tenant", "level"], name="esc_tnt_level_idx"),
        ]

    def __str__(self):
        return f"{self.number} — L{self.level} {self.issue.number}"
