"""Projects 7.4 — BudgetRevision [BVR-]: the budget document and its change control in one row.

One table realizes two of 7.4's bullets: bullet **1 Budget Planning & Estimation** (the revision
is the planning document its ``lines`` sum up) and bullet **5 Change Control & Budget Revisions**
(the revision IS the change vehicle — submit → approve/reject → activate/re-baseline).

The **cost baseline is the approved revision**: the one row per project with ``status="approved"``
*and* ``activated_at`` stamped. There is deliberately NO ``is_active`` boolean and no
``CostBaseline``/``BSL`` model — the activate verb keeps the invariant inside
``transaction.atomic()`` (the ``ScheduleBaseline`` precedent: MySQL/MariaDB cannot enforce a
partial unique index, and a constraint Django silently declines to create would be a lie in the
schema). ``approve`` does NOT activate — two ``approved`` rows may coexist while the governance
step that picks one is pending — so ``bvr_activate`` supersedes every other ``approved`` revision
of the project, keeping their ``activated_at`` as history.

``decision_notes`` is verb-written evidence (``bvr_reject``), never a form field — the
``ProjectRequest`` precedent: a field a gated verb writes must not also be POST-settable through
the ungated edit form, or any member could rewrite the admin's stated rationale.

``amount_delta`` (this revision's lines minus the active baseline's) is the approver's headline
number — computed on read, never a stored column, like every money figure in this sub-module.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class BudgetRevision(TenantNumbered):
    NUMBER_PREFIX = "BVR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("superseded", "Superseded"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="budget_revisions")
    #: 0 = the original plan; each approved change request raises it by one.
    revision_no = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255)
    #: Face-value sums only — nothing is converted (FX is 2.x/7.15's). Global table (L29).
    currency = models.ForeignKey(
        "accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="budget_revisions")
    #: Verb-driven (submit/approve/reject/activate) — OFF the form, like every governance state.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    reason = models.TextField(help_text="Why this change is being proposed.")
    impact_note = models.TextField(
        blank=True, help_text="Cost impact analysis — what moves, by how much.")
    #: 7.4 RECORDS the schedule-impact note; schedule-impact ownership stays with 7.2/7.7.
    schedule_impact_note = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bvr_requested")
    requested_at = models.DateTimeField(null=True, blank=True, editable=False)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="bvr_decided")
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The rejection rationale — written ONLY by ``bvr_reject``, never by a form.
    decision_notes = models.TextField(blank=True)
    #: The re-baseline stamp — set by ``bvr_activate`` only. ``status="approved"`` + this set
    #: means THIS row is the cost baseline the project is managed against.
    activated_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="bvr_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number"), ("tenant", "project", "revision_no")
        indexes = [
            models.Index(fields=["tenant", "project", "status"], name="bvr_tnt_prj_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_locked(self):
        """Approved and superseded rows are frozen cost history — edit/delete refuse them."""
        return self.status in ("approved", "superseded")

    @property
    def active_revision(self):
        """The project's cost baseline: the approved revision activated most recently."""
        return (self.project.budget_revisions
                .filter(status="approved", activated_at__isnull=False)
                .order_by("-activated_at")
                .first())

    def lines_sum(self, revision=None):
        """q2-clamped sum of one revision's budget lines (``None`` = this revision)."""
        target = self if revision is None else revision
        return q2(target.lines.aggregate(total=Sum("amount"))["total"])

    @property
    def amount_delta(self):
        """This revision's total against the active baseline's — the approver's headline.

        With no active revision yet (first plan) the baseline sum is zero, so the delta is the
        whole plan. Comparing against THIS row reports 0 by definition.
        """
        active = self.active_revision
        baseline_total = ZERO if active is None else self.lines_sum(active)
        return q2(self.lines_sum() - baseline_total)
