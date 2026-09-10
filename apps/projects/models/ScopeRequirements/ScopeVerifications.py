"""Projects 7.7 — ScopeVerification [SVR-]: a deliverable inspection and its acceptance decision.

Bullet 5 ("Scope Verification & Control — Deliverable inspection, scope creep alerts, and formal
acceptance workflows"). This row is the inspection record: **what** was inspected (``deliverable``
plus the optional 7.2 ``wbs_node`` it came from), **how** (``method``), **what the inspector found**
(``result`` and ``findings``) and **whether the customer accepted it** (``acceptance_status`` with
its ``accepted_by``/``accepted_at`` evidence pair).

**The acceptance decision is a formal workflow, not an editable column.** ``acceptance_status``,
``decision_note`` and the acceptance stamps are OFF the form and move only through the three
audited verbs — ``svr_accept`` (any member), ``svr_reject`` and ``svr_waive`` (admins). Rejecting a
deliverable requires a written reason, because a rejection without one is not actionable.

**Scope-creep alerts are computed, not stored.** The creep signal is the approved-and-implemented
change requests aggregated per month on the ``scope_matrix`` page — it is a *view over* the change
register, and a stored alert row would go stale the moment a change is approved (the 7.5
"no stored simulation" ruling). Nothing on this table is a creep figure.

**Boundaries (L36):** the deliverable may be a 7.2 ``ProjectTask`` and the requirement may be a
7.7 ``Requirement``; both are string FKs. Quality *testing* protocol and defect tracking are 7.6's
(``quality``) — this table records the scope acceptance gate, not a QA test run.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ScopeVerification(TenantNumbered):
    NUMBER_PREFIX = "SVR"

    METHOD_CHOICES = [
        ("inspection", "Inspection"),
        ("test", "Test"),
        ("demonstration", "Demonstration"),
        ("analysis", "Analysis"),
        ("review", "Peer Review"),
    ]
    RESULT_CHOICES = [
        ("pass", "Pass"),
        ("conditional", "Conditional Pass"),
        ("fail", "Fail"),
    ]
    ACCEPTANCE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("waived", "Waived"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="scope_verifications")
    #: The 7.2 work package inspected, when the deliverable maps onto one.
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scope_verifications")
    #: The 7.7 requirement this inspection verifies — the traceability matrix's second edge.
    requirement = models.ForeignKey(
        "projects.Requirement", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scope_verifications")
    #: What was actually put in front of the reviewer. Free text on purpose: a deliverable is not
    #: always a WBS node, and forcing one would hide the ones that are not.
    deliverable = models.CharField(max_length=255)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES, default="inspection")
    result = models.CharField(max_length=12, choices=RESULT_CHOICES, default="pass")
    #: Verb-driven (accept/reject/waive) — OFF the form.
    acceptance_status = models.CharField(
        max_length=12, choices=ACCEPTANCE_STATUS_CHOICES, default="pending")
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inspected_scope_deliverables")
    inspection_date = models.DateField(default=timezone.localdate)
    #: The inspector's notes — what passed, what was conditional, what failed and why.
    findings = models.TextField(blank=True)
    #: Verb-written — the acceptance decision's reasoning.
    decision_note = models.TextField(blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="accepted_scope_deliverables")
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="svr_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="svr_tnt_project_idx"),
            models.Index(fields=["tenant", "acceptance_status"], name="svr_tnt_status_idx"),
            models.Index(fields=["tenant", "result"], name="svr_tnt_result_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.deliverable}"

    # -- derived predicates (never stored) -------------------------------------------------------

    @property
    def is_decided(self):
        """A decision has been taken — the formal workflow is closed."""
        return self.acceptance_status != "pending"

    @property
    def is_accepted(self):
        """Accepted or waived — the deliverable cleared the gate either way."""
        return self.acceptance_status in ("accepted", "waived")

    @property
    def is_locked(self):
        """A decided inspection is frozen evidence — edit/delete refuse it."""
        return self.is_decided

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the verification."})
        if self.requirement_id and self.project_id \
                and self.requirement.project_id != self.project_id:
            raise ValidationError(
                {"requirement": "The requirement must belong to the same project as the "
                                "verification."})
