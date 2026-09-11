"""Projects 7.5 — RiskResponseAction [RRA-]: one concrete action that executes a risk response.

Bullet **3 Response Planning** owns this row. A ``ProjectRisk`` records the *strategy* (avoid /
mitigate / transfer / accept / exploit / escalate) and the contingency plan; this row is the
committed work that makes the strategy real — who does it, by when, at what cost, and behind which
trigger. The register's detail page lists its actions, so a plan with no action is visibly a plan
with no owner.

**Everything scored is DERIVED, never stored.** ``residual_score`` is the post-action
``residual_probability × residual_impact`` pair and ``is_overdue`` is a pure function of
``due_date`` and ``status`` — both are Python properties (the 7.1 ROI / 7.4 EVM ruling). A stored
copy would go stale the instant the pair or the status changed.

**The lifecycle is verb-driven.** ``status``, ``completed_at`` and ``created_by`` are off the form;
``rra_complete`` is the only writer of the completion stamp, so the evidence trail keeps its
timestamps. ``is_locked`` (``status == "completed"``) is what makes edit/delete refuse a finished
row.

**Boundary (L36):** ``risk`` is FK'd **by string** into the 7.5 register — the risk model is not
re-declared here. This row carries its own owner, due date and cost; the risk's ``response_strategy``
stays the risk's column, and the cost recorded here is an action estimate, not a 7.4 posting
(Ruling 4 — one writer per column).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class RiskResponseAction(TenantNumbered):
    NUMBER_PREFIX = "RRA"

    #: The same six strategies ``ProjectRisk.RESPONSE_STRATEGY_CHOICES`` offers — one vocabulary
    #: for the risk and the actions that execute its response.
    STRATEGY_CHOICES = [
        ("avoid", "Avoid"),
        ("mitigate", "Mitigate"),
        ("transfer", "Transfer"),
        ("accept", "Accept"),
        ("exploit", "Exploit"),
        ("escalate", "Escalate"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    risk = models.ForeignKey(
        "projects.ProjectRisk", on_delete=models.CASCADE, related_name="response_actions")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    strategy = models.CharField(max_length=12, choices=STRATEGY_CHOICES, default="mitigate")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="risk_actions")
    due_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="The action's estimated cost — an estimate, not a 7.4 posting.")
    #: The observable event that starts the action — an action with no trigger is a wish.
    trigger = models.TextField(blank=True)
    #: Verb-driven (complete) — OFF the form, so the completion stamp stays the verb's to write.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned")
    #: The post-action estimate — a second opinion on the same row, not a second table.
    residual_probability = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    residual_impact = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="rra_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "risk"], name="rra_tnt_risk_idx"),
            models.Index(fields=["tenant", "status"], name="rra_tnt_status_idx"),
            models.Index(fields=["tenant", "owner"], name="rra_tnt_owner_idx"),
            models.Index(fields=["tenant", "due_date"], name="rra_tnt_due_idx"),
            # The ``?strategy=`` choice filter.
            models.Index(fields=["tenant", "strategy"], name="rra_tnt_strategy_idx"),
            # ``Meta.ordering`` is ``-created_at`` — every rra_list render sorts the tenant's whole
            # action set to hand back the first page, so the ordering needs a matching index.
            models.Index(fields=["tenant", "-created_at"], name="rra_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def is_overdue(self):
        """Due date passed and the action is still live. Uses ``timezone.localdate()`` (L16)."""
        if not self.due_date:
            return False
        return (self.due_date < timezone.localdate()
                and self.status not in ("completed", "cancelled"))

    @property
    def residual_score(self):
        """``None`` until BOTH residual ordinals are set — a half-entered residual is not a score."""
        if self.residual_probability is None or self.residual_impact is None:
            return None
        return self.residual_probability * self.residual_impact

    @property
    def is_locked(self):
        """A completed action is frozen evidence — edit/delete refuse it."""
        return self.status == "completed"
