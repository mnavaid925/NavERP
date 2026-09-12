"""Projects 7.6 — DeliverableInspection [QCI-]: one inspection of one deliverable against a plan.

This row realizes **two** NavERP bullets, and that is deliberate:

* bullet **3 (Quality Control & Inspections)** — the execution record: a deliverable checked
  against the plan's criteria, with the result (``result``), the date it was inspected
  (``inspected_date``) and the findings.
* bullet **5 (Deliverable Acceptance & Sign-off)** — the acceptance decision: ``usage_decision``
  plus the ``qci_accept`` verb that stamps the acceptor, the customer party and the moment.

They share one table because **acceptance *is* the terminal inspection decision** — the same
deliverable, the same criteria, the same evidence row, one step further along. A separate
``AcceptanceSignOff`` table would duplicate the row it accepts and give the workspace two records
of the same gate that could disagree.

**The class is ``DeliverableInspection``, not ``QualityInspection``.** ``QualityInspection`` is
already taken by ``apps/scm/models/QualityManagement/QualityInspections.py`` — scm 4.9 owns the
enterprise QMS (``NonConformance`` / ``CapaAction`` / ``QualityAudit`` / ``QualityInspection``).
This table is project-deliverable-scoped only; do not rename it to match the enterprise class.

**Everything derived is a Python property, never a column.** ``is_overdue``, ``is_locked``,
``defect_count`` and ``is_acceptance`` are pure functions of the status and the dates (the 7.1 ROI
/ 7.4 EVM ruling): a stored flag is stale the moment a date or a status is edited.
``is_overdue`` reads ``timezone.localdate()`` — the same clock the rest of 7.6 uses (L16).

**Verb-driven lifecycle.** ``status``, ``usage_decision``, ``accepted_by``, ``accepted_by_party``,
``accepted_at``, ``acceptance_note`` and ``created_by`` are all OFF the model form:
``qci_record``, ``qci_accept`` and ``qci_reject`` are the only writers of those columns, so the
evidence trail keeps its stamps. ``is_locked`` (a terminal status, or a decision already taken) is
what makes edit/delete refuse a finished row.

**Boundaries (L36):** ``project``, ``wbs_node``, ``quality_plan`` and ``milestone`` are all FK'd
**by string** into 7.1/7.2 and this sub-module's own entity 1 — none is re-declared here. The
milestone is 7.2's phase gate (Ruling 5), not a second one. The usage-decision vocabulary is a
deliberate superset of scm 4.9's (Ruling 4). There is no money column (Ruling 7 — a cost of
quality is a 7.4 ``ProjectExpense``), so this module declares no ``DecimalField``.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class DeliverableInspection(TenantNumbered):
    NUMBER_PREFIX = "QCI"

    INSPECTION_TYPE_CHOICES = [
        ("review", "Review"),
        ("testing", "Testing"),
        ("demonstration", "Demonstration"),
        ("walkthrough", "Walkthrough"),
        ("acceptance", "Acceptance"),
    ]
    RESULT_CHOICES = [
        ("pending", "Pending"),
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("conditional", "Conditional"),
        ("not_applicable", "Not Applicable"),
    ]
    #: A deliberate superset of scm 4.9's QualityInspection usage-decision vocabulary (Ruling 4):
    #: scm carries the four values below minus ``rework`` (it is a NonConformance disposition
    #: there). ``rework`` is kept here as vocabulary for the manual rework loop — no 7.6 verb
    #: writes it today, and every consumer reads it safely.
    USAGE_DECISION_CHOICES = [
        ("pending", "Pending"),
        ("accept", "Accept"),
        ("accept_with_deviation", "Accept with Deviation"),
        ("reject", "Reject"),
        ("rework", "Rework"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("on_hold", "On Hold"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="quality_inspections")
    #: The deliverable inspected. Same-project ``clean()`` guard — the ``ProjectMilestone.anchor_task``
    #: pattern.
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_inspections")
    #: The entity-1 plan whose criteria this inspection tests. Optional, but same-project guarded.
    quality_plan = models.ForeignKey(
        "projects.QualityPlan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inspections")
    #: The 7.2 phase gate this acceptance is reviewed at. 7.2's gate, not re-declared (Ruling 5).
    milestone = models.ForeignKey(
        "projects.ProjectMilestone", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_inspections")
    title = models.CharField(max_length=255)
    #: The testing protocol / procedure the inspection follows. Free text.
    description = models.TextField(blank=True)
    inspection_type = models.CharField(
        max_length=16, choices=INSPECTION_TYPE_CHOICES, default="review")
    #: When the inspection is due — drives ``is_overdue`` while it has not yet been executed.
    planned_date = models.DateField(null=True, blank=True)
    #: The date the inspection was actually executed — stamped by ``qci_record``.
    inspected_date = models.DateField(null=True, blank=True)
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conducted_inspections")
    #: Bullet 3's outcome. Recorded by ``qci_record``, never chosen on the generic edit form.
    #: ``max_length=14`` fits ``not_applicable`` — the same width scm 4.9's ``QualityInspection
    #: .result`` uses for the same vocabulary.
    result = models.CharField(max_length=14, choices=RESULT_CHOICES, default="pending")
    #: Bullet 5's decision. Moved by ``qci_accept`` / ``qci_reject`` — OFF the model form.
    usage_decision = models.CharField(
        max_length=24, choices=USAGE_DECISION_CHOICES, default="pending")
    findings = models.TextField(blank=True)
    #: Stamped by ``qci_accept`` — read-only evidence of who signed the deliverable off.
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="accepted_inspections")
    #: The external / customer acceptor. A ``core.Party`` scoped to the tenant's clients in the form.
    accepted_by_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="accepted_inspections")
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: Conditions / reservations attached to the acceptance. Written by ``qci_accept``.
    acceptance_note = models.TextField(blank=True)
    #: Verb-driven (record / accept / reject) — OFF the form, so the evidence trail keeps its stamps.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="qci_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="qci_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="qci_tnt_status_idx"),
            models.Index(fields=["tenant", "result"], name="qci_tnt_result_idx"),
            models.Index(fields=["tenant", "usage_decision"], name="qci_tnt_decision_idx"),
            models.Index(fields=["tenant", "wbs_node"], name="qci_tnt_wbs_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def is_overdue(self):
        """Planned date passed while the inspection has not been executed. Uses
        ``timezone.localdate()`` (L16)."""
        if not self.planned_date:
            return False
        return (self.planned_date < timezone.localdate()
                and self.inspected_date is None
                and self.status in ("planned", "in_progress"))

    @property
    def is_locked(self):
        """A terminal status, or a decision already taken, freezes the row — edit/delete refuse it."""
        return (self.status in ("passed", "failed", "cancelled")
                or self.usage_decision != "pending")

    @property
    def defect_count(self):
        """How many punch-list items this inspection found — a read of the child table, never a
        stored count."""
        return self.defects.count()

    @property
    def is_acceptance(self):
        """True for the bullet-5 acceptance inspections — the acceptance page lenses on this."""
        return self.inspection_type == "acceptance"

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the inspection."})
        if self.quality_plan_id and self.project_id \
                and self.quality_plan.project_id != self.project_id:
            raise ValidationError(
                {"quality_plan": "The quality plan must belong to the same project as the "
                                 "inspection."})
        if self.milestone_id and self.project_id \
                and self.milestone.project_id != self.project_id:
            raise ValidationError(
                {"milestone": "The milestone must belong to the same project as the inspection."})
