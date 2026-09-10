"""Projects 7.6 — QualityPlan [QPL-]: the acceptance criteria a deliverable is measured against.

The plan is where bullet **1 (quality planning & standards)** lives: it names the deliverable, the
criteria that define "done", the verification method that will demonstrate it and the standard or
regulation it answers to. It is also the anchor bullets 3 and 5 inspect against — a
``DeliverableInspection`` points back at the plan whose criteria it tests, and a ``QualityDefect``
points back at the criterion it violates.

**Everything is a field, never a store.** ``standard_reference`` and ``regulatory_requirement`` are
free text: a standards master is 7.19's (Ruling 3), and a second standards table would give the
workspace two places to look for the same clause. Likewise there is no money column (Ruling 7 — a
quality cost is a 7.4 ``ProjectExpense``), so this module imports ``q2()`` but never uses it.

**Verb-driven lifecycle.** ``status`` is OFF the form. A plan is approved (``draft`` → ``active``,
stamping the approver and the moment) or superseded (``active`` → ``superseded``, admin-only —
L27). ``is_review_overdue`` and ``is_locked`` are derived Python properties, never columns, so they
cannot go stale the instant a date or a status is edited (the 7.1 ROI / 7.4 EVM ruling).

**Boundaries (L36):** the project, the WBS node and the source risk are all FK'd **by string**
into 7.1/7.2/7.5 — none is re-declared here. The source risk is the 7.5 quality-category threat or
opportunity this plan mitigates; the plan does not become a second risk register.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class QualityPlan(TenantNumbered):
    NUMBER_PREFIX = "QPL"

    VERIFICATION_METHOD_CHOICES = [
        ("inspection", "Inspection"),
        ("testing", "Testing"),
        ("demonstration", "Demonstration"),
        ("review", "Review"),
        ("analysis", "Analysis"),
        ("audit", "Audit"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("superseded", "Superseded"),
        ("closed", "Closed"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="quality_plans")
    #: The deliverable the criteria measure. Same-project ``clean()`` guard — the
    #: ``ProjectMilestone.anchor_task`` pattern.
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_plans")
    #: The 7.5 quality-category risk this plan mitigates. A lens into the risk register, not a
    #: second one — the risk's own columns stay 7.5's to write.
    source_risk = models.ForeignKey(
        "projects.ProjectRisk", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_plans")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    #: Bullet 1's core: the criteria that define acceptance. Required — a plan with no criteria
    #: cannot be inspected against.
    acceptance_criteria = models.TextField()
    verification_method = models.CharField(
        max_length=16, choices=VERIFICATION_METHOD_CHOICES, default="inspection")
    #: Free text ("ISO 9001:2015", "21 CFR Part 11") — a standards master is 7.19's (Ruling 3).
    standard_reference = models.CharField(max_length=120, blank=True)
    #: The clause / requirement text this plan answers to. Free text, same ruling.
    regulatory_requirement = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_quality_plans")
    #: Verb-driven (approve / supersede) — OFF the form, so the evidence trail keeps its stamps.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    #: The next scheduled review of this plan — drives ``is_review_overdue``.
    planned_review_date = models.DateField(null=True, blank=True)
    #: Stamped by ``qpl_approve`` — read-only evidence of who activated the plan and when.
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="approved_quality_plans")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="qpl_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="qpl_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="qpl_tnt_status_idx"),
            models.Index(fields=["tenant", "wbs_node"], name="qpl_tnt_wbs_idx"),
            models.Index(fields=["tenant", "-created_at"], name="qpl_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def is_review_overdue(self):
        """Review date passed while the plan is still live. Uses ``timezone.localdate()`` (L16)."""
        if not self.planned_review_date:
            return False
        return (self.planned_review_date < timezone.localdate()
                and self.status in ("draft", "active"))

    @property
    def is_locked(self):
        """Superseded and closed plans are frozen evidence — edit/delete refuse them."""
        return self.status in ("superseded", "closed")

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the plan."})
        if self.source_risk_id and self.project_id \
                and self.source_risk.project_id != self.project_id:
            raise ValidationError(
                {"source_risk": "The source risk must belong to the same project as the plan."})
