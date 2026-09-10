"""Projects 7.7 — ScopeChangeRequest [SCR-]: a scope change proposal with its impact analysis.

Bullet 4 ("Change Request Management — Scope change proposals, impact analysis on
schedule/cost/quality, and CCB decisions") in one row. The three impact dimensions are recorded
side by side — ``schedule_impact_days`` (time), ``cost_impact`` (money) and
``quality_impact``/``quality_note`` (the one dimension that is genuinely ordinal) — and the CCB
decision is the audited approve/reject verb pair, not an editable status column.

**The CCB is the change control board, and the board's decision is evidence.** ``status``,
``decision_note`` and ``decided_by``/``decided_at`` are OFF the form: a decision is minted by the
``scr_approve`` / ``scr_reject`` verbs (both ``@tenant_admin_required``), so the register keeps its
approval trail exactly the way 7.1's charter gate and 7.5's realize/close pair do.

**Two FK bridges, one line each (L36).** ``requirement`` names the 7.7 requirement the change
rewrites, and ``risk`` names the 7.5 ``ProjectRisk`` that motivated it — the risk → scope-change
link 7.5's own research deferred to this sub-module. Neither is re-declared here; both are string
FKs into their owning app.

**No second budget revision.** ``cost_impact`` is the *proposal's* impact, recorded here for the
CCB to weigh. Writing it into 7.4's ``BudgetRevision`` / ``CostControlAccount`` is 7.4's writer
(Ruling: one writer per column) — this row sizes the change, it does not re-baseline the budget.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ScopeChangeRequest(TenantNumbered):
    NUMBER_PREFIX = "SCR"

    SOURCE_CHOICES = [
        ("internal", "Internal"),
        ("client", "Client"),
        ("regulatory", "Regulatory"),
        ("vendor", "Vendor"),
        ("technical", "Technical"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    QUALITY_IMPACT_CHOICES = [
        ("none", "None"),
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("implemented", "Implemented"),
    ]

    #: The ordinal quality dimension as a weight, so "is this change material?" is a documented
    #: rule rather than a vibe (the 7.1 ``RISK_DISCOUNT`` idiom).
    QUALITY_WEIGHT = {"none": 0, "low": 1, "medium": 2, "high": 3}
    #: A change is HIGH IMPACT when any one of these thresholds is crossed. Deliberately flat
    #: documented constants, not a per-tenant config table (per-tenant thresholds are 7.19's).
    HIGH_COST = Decimal("50000")
    HIGH_SCHEDULE_DAYS = 10

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="scope_changes")
    #: The requirement this change rewrites, when it targets one.
    requirement = models.ForeignKey(
        "projects.Requirement", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="change_requests")
    #: The 7.5 risk that motivated the change — the risk → scope-change bridge, one string FK.
    risk = models.ForeignKey(
        "projects.ProjectRisk", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scope_changes")
    title = models.CharField(max_length=255)
    description = models.TextField()
    #: Why the change is worth making — the argument the CCB weighs.
    justification = models.TextField(blank=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="internal")
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default="medium")
    #: Impact dimension 1 — time.
    schedule_impact_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Days of schedule impact if approved.")
    #: Impact dimension 2 — money. Recorded for the CCB; 7.4 owns the re-baseline.
    cost_impact = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Budget impact if approved. Sizing only — 7.4 owns the budget re-baseline.")
    #: Impact dimension 3 — quality (ordinal) plus its explanation.
    quality_impact = models.CharField(
        max_length=12, choices=QUALITY_IMPACT_CHOICES, default="none")
    quality_note = models.TextField(blank=True)
    #: Verb-driven (submit/review/approve/reject/implement) — OFF the form.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    #: Verb-written — the CCB's reasoning, captured by the reject verb.
    decision_note = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requested_scope_changes")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="decided_scope_changes")
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    implemented_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="scr_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="scr_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="scr_tnt_status_idx"),
            models.Index(fields=["tenant", "priority"], name="scr_tnt_priority_idx"),
            models.Index(fields=["tenant", "source"], name="scr_tnt_source_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def impact_weight(self):
        """The ordinal quality impact as a weight — the ``QUALITY_WEIGHT`` map's only reader."""
        return self.QUALITY_WEIGHT.get(self.quality_impact, 0)

    @property
    def is_high_impact(self):
        """Any one crossed threshold makes the change material — the documented rule."""
        return (self.cost_impact >= self.HIGH_COST
                or (self.schedule_impact_days or 0) >= self.HIGH_SCHEDULE_DAYS
                or self.quality_impact == "high")

    @property
    def is_pending(self):
        """Still in front of the CCB — the ``?pending=1`` approval-queue lens."""
        return self.status in ("draft", "submitted", "under_review")

    @property
    def is_approved(self):
        return self.status in ("approved", "implemented")

    @property
    def is_locked(self):
        """An implemented change is frozen evidence — edit/delete refuse it."""
        return self.status == "implemented"

    def clean(self):
        super().clean()
        if self.requirement_id and self.project_id \
                and self.requirement.project_id != self.project_id:
            raise ValidationError(
                {"requirement": "The requirement must belong to the same project as the change "
                                "request."})
        if self.risk_id and self.project_id and self.risk.project_id != self.project_id:
            raise ValidationError(
                {"risk": "The risk must belong to the same project as the change request."})
