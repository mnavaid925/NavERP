"""Projects 7.5 — ProjectRisk [RSK-]: one identified threat or opportunity on one project.

The register row is where four of the five 7.5 bullets meet: **1 Identification & Register** (this
is the register), **2 Qualitative & Quantitative Analysis** (the probability × impact pair and the
EMV inputs), **3 Response Planning** (the strategy, the trigger and the contingency plan) and
**5 Monitoring** (the review date and, once closed, the lesson).

**Everything scored is DERIVED, never stored.** ``score``, ``severity_band``, ``emv``, the residual
pair and ``is_review_overdue`` are Python properties — the 7.1 ROI / 7.4 EVM ruling. A stored score
is a second source of truth for a number that is already a pure function of its inputs, and it goes
stale the instant someone edits the impact.

**Two documented constant maps, no config tables.** ``PROBABILITY_PCT`` converts the 1–5 ordinal
into the percentage the EMV and the Monte Carlo draw use (the 7.1 ``RISK_DISCOUNT`` idiom), and
``SEVERITY_BANDS`` maps the 1–25 score onto four bands. Risk appetite as a *per-tenant* setting is
7.19's master data; this pass pins the documented default (Ruling 6).

**Boundaries (L36):** the project, the WBS node and the contingency control account are all FK'd
**by string** into 7.1/7.2/7.4 — none is re-declared here. ``contingency_account`` is a read-only
lens: it names the CA whose 7.4 reserve this risk justifies, and the write to that CA's
``contingency`` column stays 7.4's (Ruling 4 — one writer per column).

``lessons_learned`` is a FIELD on the row, not a store: the knowledge repository is 7.10's, and a
second lessons table would give the workspace two places to look (Ruling 3).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings

#: Ordinal → the percentage used by ``emv`` and by the Monte Carlo Bernoulli draw. A documented
#: flat map, deliberately not a fitted distribution (the 7.1 ``RISK_DISCOUNT`` idiom).
PROBABILITY_PCT = {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}


class ProjectRisk(TenantNumbered):
    NUMBER_PREFIX = "RSK"

    CATEGORY_CHOICES = [
        ("technical", "Technical"),
        ("schedule", "Schedule"),
        ("cost", "Cost"),
        ("resource", "Resource"),
        ("external", "External"),
        ("organizational", "Organizational"),
        ("quality", "Quality"),
        ("compliance", "Compliance"),
        ("other", "Other"),
    ]
    RISK_TYPE_CHOICES = [
        ("threat", "Threat"),
        ("opportunity", "Opportunity"),
    ]
    RESPONSE_STRATEGY_CHOICES = [
        ("avoid", "Avoid"),
        ("mitigate", "Mitigate"),
        ("transfer", "Transfer"),
        ("accept", "Accept"),
        ("exploit", "Exploit"),
        ("escalate", "Escalate"),
    ]
    STATUS_CHOICES = [
        ("identified", "Identified"),
        ("assessing", "Assessing"),
        ("response_planned", "Response Planned"),
        ("monitoring", "Monitoring"),
        ("realized", "Realized"),
        ("closed", "Closed"),
    ]

    #: Score band boundaries, inclusive on both ends. The keys are the values ``severity_band``
    #: returns and the values the badge templates switch on.
    SEVERITY_BANDS = {
        "low": (1, 3),
        "medium": (4, 7),
        "high": (8, 14),
        "critical": (15, 25),
    }
    #: The bands that exceed the documented default risk tolerance. A per-tenant appetite is 7.19's.
    TOLERANCE_BANDS = {"high", "critical"}

    _BAND_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="risks")
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="risks")
    title = models.CharField(max_length=255)
    description = models.TextField()
    #: The "If … then" pair the register's cause/effect columns render.
    cause = models.TextField(blank=True)
    effect = models.TextField(blank=True)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="other")
    risk_type = models.CharField(
        max_length=12, choices=RISK_TYPE_CHOICES, default="threat",
        help_text="ISO 31000 is two-sided: a threat hurts, an opportunity helps.")
    probability = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 (rare) … 5 (almost certain).")
    impact = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 (negligible) … 5 (severe).")
    cost_impact = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Monetary exposure if the risk is realized — the EMV and simulation input.")
    #: Recorded, not simulated: a WBS-network schedule simulation needs 7.2 activity uncertainty.
    schedule_impact_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Days of schedule exposure if realized (recorded only).")
    response_strategy = models.CharField(
        max_length=12, choices=RESPONSE_STRATEGY_CHOICES, default="mitigate")
    response_note = models.TextField(blank=True)
    #: The observable event that activates the response — a risk with no trigger is a wish.
    trigger = models.TextField(blank=True)
    contingency_plan = models.TextField(blank=True)
    #: Verb-driven (realize/close/reopen) — OFF the form, so the evidence trail keeps its stamps.
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="identified")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_risks")
    identified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="raised_risks")
    identified_date = models.DateField(default=timezone.localdate)
    review_date = models.DateField(
        null=True, blank=True, help_text="The next scheduled review of this risk.")
    #: The post-response estimate — a second opinion on the same row, not a second table.
    residual_probability = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    residual_impact = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    #: Read-only lens: the CA whose 7.4 contingency reserve this risk justifies. 7.5 SIZES the
    #: reserve (the EMV / P80 delta); the write to ``CostControlAccount.contingency`` stays 7.4's.
    contingency_account = models.ForeignKey(
        "projects.CostControlAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="risks")
    #: The closed-row takeaway. A field, NOT a store — the knowledge repository is 7.10's.
    lessons_learned = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="rsk_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="rsk_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="rsk_tnt_status_idx"),
            models.Index(fields=["tenant", "category"], name="rsk_tnt_category_idx"),
            models.Index(fields=["tenant", "risk_type"], name="rsk_tnt_rtype_idx"),
            models.Index(fields=["tenant", "-created_at"], name="rsk_tnt_created_idx"),
            # The register's pinned derived lenses: ``?review_due=1``/``?overdue=1`` filter on
            # review_date, and ``?owner=`` deserves more than the bare FK index.
            models.Index(fields=["tenant", "review_date"], name="rsk_tnt_review_idx"),
            models.Index(fields=["tenant", "owner"], name="rsk_tnt_owner_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def score(self):
        """The 1–25 qualitative score. A pure function of two columns — never a column."""
        return self.probability * self.impact

    @property
    def severity_band(self):
        """``low`` / ``medium`` / ``high`` / ``critical`` from :attr:`SEVERITY_BANDS`."""
        for band, (low, high) in self.SEVERITY_BANDS.items():
            if low <= self.score <= high:
                return band
        return "low"

    def get_severity_band_display(self):
        """Hand-written: Django does NOT generate ``get_FOO_display`` for a property, and a
        template that renders ``obj.get_severity_band_display`` without it shows an empty cell
        (the ``ProjectStakeholder.get_engagement_strategy_display`` precedent)."""
        return self._BAND_LABELS.get(self.severity_band, self.severity_band.title())

    @property
    def emv(self):
        """Expected monetary value: ``cost_impact × P(probability)``."""
        return q2(self.cost_impact * PROBABILITY_PCT.get(self.probability, 0) / 100)

    @property
    def exposure(self):
        """The burn-down sum term. EMV is the exposure figure this register reports."""
        return self.emv

    @property
    def residual_score(self):
        """``None`` until BOTH residual ordinals are set — a half-entered residual is not a score."""
        if self.residual_probability is None or self.residual_impact is None:
            return None
        return self.residual_probability * self.residual_impact

    @property
    def residual_band(self):
        score = self.residual_score
        if score is None:
            return None
        for band, (low, high) in self.SEVERITY_BANDS.items():
            if low <= score <= high:
                return band
        return "low"

    @property
    def residual_emv(self):
        """The expected exposure after the planned response — 0 until a residual is entered."""
        if self.residual_probability is None:
            return Decimal("0")
        return q2(self.cost_impact * self.residual_probability / 100)

    @property
    def is_review_overdue(self):
        """Review date passed and the risk is still live. Uses ``timezone.localdate()`` (L16)."""
        if not self.review_date:
            return False
        return (self.review_date < timezone.localdate()
                and self.status not in ("realized", "closed"))

    @property
    def is_locked(self):
        """Realized and closed rows are frozen evidence — edit/delete refuse them."""
        return self.status in ("realized", "closed")

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the risk."})
        if self.contingency_account_id and self.project_id \
                and self.contingency_account.project_id != self.project_id:
            raise ValidationError(
                {"contingency_account": "The control account must belong to the same project as "
                                        "the risk."})
