"""Projects 7.6 — QualityReview [QRV-]: one structured quality event, assurance or improvement.

This row realizes **two** NavERP bullets, discriminated by ``review_type``:

* bullet **2 (Quality Assurance)** — ``methodology_review`` / ``compliance_check`` / ``gate_review``:
  a planned check that a process, a compliance obligation or a stage gate is being met.
* bullet **4 (Continuous Improvement)** — ``kaizen_event`` / ``retrospective`` /
  ``maturity_assessment``: a learning event whose output is an improvement action with an owner
  and a due date.

Both are "a structured quality event with a checklist, findings, a reviewer and follow-up", so they
are **deliberately consolidated into one table**. A separate ``QualityImprovement`` table would fork
the whole CRUD surface — register, form, detail, permissions, numbering — to express a single choice
field, and the improvement block (``improvement_action`` / ``improvement_owner`` /
``improvement_due_date`` / ``improvement_status``) is **planning data on the form**, not a
verb-written stamp, so it belongs on the row either way.

**Everything derived is a Python property, never a column.** ``is_improvement_overdue`` and
``is_locked`` are pure functions of the dates and the status (the 7.1 ROI / 7.4 EVM ruling): a stored
flag is stale the moment the due date or the status is edited. Both read ``timezone.localdate()`` —
the same clock the rest of 7.6 uses (L16).

**Verb-driven lifecycle.** ``status``, ``closed_at`` and ``created_by`` are OFF the model form:
``qrv_report`` and ``qrv_close`` are the only writers of the status transition and its timestamp, so
the evidence trail keeps its stamps. ``is_locked`` (``closed``/``cancelled``) is what makes
edit/delete refuse a finished row.

**Boundaries (L36):** ``project``, ``wbs_node`` and ``quality_plan`` are all FK'd **by string** into
7.1/7.2 and this sub-module's own entity 1 — none is re-declared here. ``checklist`` is free text on
the row: a reusable checklist library is 7.19's master data (Ruling 3). ``maturity_score`` is a plain
1–5 rating — there is **no stored maturity table** and no score column beyond this one rating (the
process-maturity *assessment* is a computed page, not this model).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class QualityReview(TenantNumbered):
    NUMBER_PREFIX = "QRV"

    #: The assurance types (bullet 2) and the improvement types (bullet 4) share one vocabulary so
    #: the register can be read whole or lensed to either half.
    REVIEW_TYPE_CHOICES = [
        ("methodology_review", "Methodology Review"),
        ("compliance_check", "Compliance Check"),
        ("gate_review", "Gate Review"),
        ("kaizen_event", "Kaizen Event"),
        ("retrospective", "Retrospective"),
        ("maturity_assessment", "Maturity Assessment"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("reported", "Reported"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    #: The improvement action's own lifecycle — planning data on the form, not a verb-written stamp.
    IMPROVEMENT_STATUS_CHOICES = [
        ("n_a", "N/A"),
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="quality_reviews")
    #: The deliverable the review examined. Same-project ``clean()`` guard — the
    #: ``ProjectMilestone.anchor_task`` pattern.
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_reviews")
    #: The entity-1 plan whose criteria this review checked against. Optional — a kaizen event need
    #: not answer to a written plan — but same-project guarded when set.
    quality_plan = models.ForeignKey(
        "projects.QualityPlan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviews")
    title = models.CharField(max_length=255)
    scope = models.TextField(blank=True)
    review_type = models.CharField(
        max_length=24, choices=REVIEW_TYPE_CHOICES, default="methodology_review")
    #: The per-review checklist items. Free text — a reusable checklist library is 7.19's (Ruling 3).
    checklist = models.TextField(blank=True)
    findings = models.TextField(blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="conducted_quality_reviews")
    review_date = models.DateField(default=timezone.localdate)
    #: Verb-driven (report / close) — OFF the form, so the evidence trail keeps its stamps.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned")
    #: A plain 1–5 rating. There is no stored maturity table and no other score column — the
    #: process-maturity *assessment* is a computed page built later (Ruling 6).
    maturity_score = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    #: Bullet 4's output: what will change, who owns it and by when. Planning data on the form.
    improvement_action = models.TextField(blank=True)
    improvement_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_quality_reviews")
    improvement_due_date = models.DateField(null=True, blank=True)
    improvement_status = models.CharField(
        max_length=12, choices=IMPROVEMENT_STATUS_CHOICES, default="n_a")
    #: Stamped by ``qrv_close`` — read-only evidence of when the review was retired.
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="qrv_created")

    class Meta:
        ordering = ["-review_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="qrv_tnt_project_idx"),
            models.Index(fields=["tenant", "review_type"], name="qrv_tnt_type_idx"),
            models.Index(fields=["tenant", "status"], name="qrv_tnt_status_idx"),
            models.Index(fields=["tenant", "improvement_status"], name="qrv_tnt_imp_idx"),
            models.Index(fields=["tenant", "-review_date"], name="qrv_tnt_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def is_improvement_overdue(self):
        """Improvement due date passed while the action is still open. Uses ``timezone.localdate()``
        (L16)."""
        if not self.improvement_due_date:
            return False
        return (self.improvement_due_date < timezone.localdate()
                and self.improvement_status in ("planned", "in_progress"))

    @property
    def is_locked(self):
        """Closed and cancelled rows are frozen evidence — edit/delete refuse them."""
        return self.status in ("closed", "cancelled")

    @property
    def is_improvement(self):
        """True for the bullet-4 review types — the improvement register lenses on this half."""
        return self.review_type in ("kaizen_event", "retrospective")

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the review."})
        if self.quality_plan_id and self.project_id \
                and self.quality_plan.project_id != self.project_id:
            raise ValidationError(
                {"quality_plan": "The quality plan must belong to the same project as the review."})
