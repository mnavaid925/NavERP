"""Procurement 6.16 Supplier Performance & Evaluation — SupplierKpi.

**What it is.** The NavERP.md "Supplier KPIs / scorecard definition" bullet: the tenant's OWN
catalogue of what "good supplier" means here. A row is a *definition*, never a measurement —
it says which number to take (``source`` / ``derived_metric``), which way is better
(``direction``), where the ok/warning/critical lines fall, how much it counts
(``weight``), and which ``scm.SupplierScorecard`` column it feeds (``maps_to_dimension``).
The measured figures live on ``SupplierKpiScore``, one row per (scorecard, KPI).

**L36 — the scorecard is SCM's.** Nothing here re-declares ``scm.SupplierScorecard``,
``scm.SupplierProfile`` or a second vendor table. ``applies_to_tier`` is matched against
``scm.SupplierProfile.tier`` at generate time; the four tier strings are mirrored LOCALLY
(:data:`TIER_CHOICES`) rather than imported, because a model module must not import a peer
app just to name four strings — the source of truth stays ``scm.SupplierProfile.TIER_CHOICES``
and the mirror is documented as such.

**:data:`DERIVED_METRIC_CHOICES` is a CLOSED registry.** Every key here is a promise that a
reviewed resolver for it exists in ``apps/procurement/performance.py``. Adding a key without a
resolver ships a KPI that silently measures nothing — the same discipline ``scm.KpiTarget.metric``
carries. Never widen this list from a template, a form or a seeder.

**Retire, never delete.** ``SupplierKpiScore.kpi`` is ``PROTECT`` on purpose: deleting a KPI
would take measured history with it. ``is_active=False`` is the retirement mechanism — a
deactivated KPI stops being picked up by generate and keeps every figure ever taken under it.

**Import discipline.** This module imports the shared toolkit from
``apps.procurement.models._base`` and NOTHING else at module top. The sibling-app reads
(``scm``, ``core``) that 6.16 needs happen inside the function that needs them, in
``apps/procurement/performance.py`` and in the views — the ``CostForecasts.py`` precedent —
because this sub-package is not wired into ``models/__init__.py`` until the Integrate phase and
a module-level sibling import that runs while ``apps.procurement.models`` is still initialising
is exactly how an import cycle gets shipped.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


#: What the KPI is about. Drives the category filter and the KPI groupings on the boards.
CATEGORY_CHOICES = [
    ("delivery", "Delivery"), ("quality", "Quality"), ("cost", "Cost"),
    ("service", "Service"), ("compliance", "Compliance"), ("esg", "ESG"),
    ("innovation", "Innovation"), ("risk", "Risk"),
]

#: The unit the measured value is read in. A label only — nothing converts between units.
UNIT_CHOICES = [
    ("pct", "Percent (%)"), ("days", "Days"), ("count", "Count"),
    ("ppm", "Parts per million"), ("money", "Money"), ("score", "Score (0-100)"),
    ("ratio", "Ratio"),
]

#: Which way is better. This is what makes a threshold mean anything at all: 2 days late is
#: bad and 98% on time is good, and only ``direction`` tells the banding which is which.
DIRECTION_CHOICES = [
    ("higher_is_better", "Higher is better"), ("lower_is_better", "Lower is better"),
]

#: Where the number comes from. ``derived`` reads the transaction spine through a resolver,
#: ``survey`` averages 360 feedback responses, ``manual`` is typed in on the score row.
SOURCE_CHOICES = [
    ("derived", "Derived from transactions"), ("survey", "360 survey"), ("manual", "Manual entry"),
]

#: CLOSED registry — one key per resolver that exists in ``apps/procurement/performance.py``.
#: NEVER add a key without a reviewed resolver (the ``scm.KpiTarget.metric`` discipline): a key
#: with no resolver is a KPI that reports nothing while looking like it reports something.
DERIVED_METRIC_CHOICES = [
    ("otd", "On-time delivery %"),
    ("otif", "On-time in-full (OTIF) %"),
    ("defect_rate", "Defect / reject rate %"),
    ("ncr_rate", "Discrepancy (NCR) rate %"),
    ("rtv_rate", "Return-to-vendor rate %"),
    ("invoice_accuracy", "Invoice accuracy %"),
    ("dispute_rate", "Dispute rate %"),
    ("dispute_days", "Mean days to resolve a dispute"),
    ("promise_adherence", "Delivery-promise adherence %"),
    ("backorder_rate", "Backorder rate %"),
    ("po_change_rate", "PO change rate %"),
    ("price_competitiveness", "Price competitiveness %"),
    ("quote_turnaround", "Quote turnaround days"),
    ("suspension_incidents", "Suspension incidents"),
]

#: How a measured value becomes a 0-100 score. See :meth:`SupplierKpi.score_and_band` — the ONE
#: scale generate, the manual edit form and the tests all band through.
SCORING_CHOICES = [
    ("band", "Band (ok / warning / critical)"), ("linear", "Linear between critical and target"),
    ("direct", "Value is the score"),
]

#: Which ``scm.SupplierScorecard`` column this KPI rolls up into. Mirrors that model's four
#: weighted dimensions exactly; blank means the KPI is measured but feeds no dimension.
DIMENSION_CHOICES = [
    ("delivery", "Delivery"), ("quality", "Quality"),
    ("price", "Price"), ("responsiveness", "Responsiveness"),
]

#: Whether the KPI is asked of every supplier or of one tier only.
APPLIES_CHOICES = [("all", "All suppliers"), ("tier", "One tier only")]

#: LOCAL mirror. SOURCE OF TRUTH: ``scm.SupplierProfile.TIER_CHOICES`` — do NOT import scm into
#: a model module just to mirror four strings. Matched against ``SupplierProfile.tier`` when
#: generate resolves which KPIs apply to a given supplier.
TIER_CHOICES = [
    ("strategic", "Strategic"), ("preferred", "Preferred"),
    ("approved", "Approved"), ("transactional", "Transactional"),
]

#: The intended review cadence. Stored only — nothing schedules off it; scorecards are
#: generated on demand, and claiming otherwise would be a promise the system does not keep.
FREQUENCY_CHOICES = [
    ("monthly", "Monthly"), ("quarterly", "Quarterly"),
    ("semiannual", "Semi-annual"), ("annual", "Annual"),
]

#: The top of the 0-100 scale every score is clamped to.
_MAX_SCORE = Decimal("100")

#: 2dp, the shape of ``SupplierKpiScore.score`` (DecimalField(5, 2)).
_SCORE_STEP = Decimal("0.01")

#: The band table — used by ``scoring_method="band"`` AND as the documented fallback when
#: ``linear`` has no usable span. ``"unknown"`` is deliberately absent: an unbanded value with
#: no linear span has no score, and ``None`` says so honestly instead of inventing a zero.
_BAND_SCORES = {"ok": _MAX_SCORE, "warning": Decimal("70"), "critical": Decimal("30")}

#: Human names for the three threshold columns, used to build ``clean()``'s messages so the
#: error names both bands rather than just pointing at a field.
_BAND_LABELS = {
    "target_value": "target",
    "warning_threshold": "warning threshold",
    "critical_threshold": "critical threshold",
}


class SupplierKpi(TenantNumbered):
    """One KPI definition [SKP-] — what to measure, which way is better, and where the lines are."""

    NUMBER_PREFIX = "SKP"

    # Re-exported through the class so templates and forms can reach them off the model
    # (``SupplierKpi.CATEGORY_CHOICES``), mirroring VendorSuspension. The module-level names
    # stay the definition; these are aliases, never a second copy to drift from.
    CATEGORY_CHOICES = CATEGORY_CHOICES
    UNIT_CHOICES = UNIT_CHOICES
    DIRECTION_CHOICES = DIRECTION_CHOICES
    SOURCE_CHOICES = SOURCE_CHOICES
    DERIVED_METRIC_CHOICES = DERIVED_METRIC_CHOICES
    SCORING_CHOICES = SCORING_CHOICES
    DIMENSION_CHOICES = DIMENSION_CHOICES
    APPLIES_CHOICES = APPLIES_CHOICES
    TIER_CHOICES = TIER_CHOICES
    FREQUENCY_CHOICES = FREQUENCY_CHOICES

    code = models.CharField(
        max_length=32,
        help_text="Master identifier used to roll this KPI up across scorecards, e.g. OTIF-01")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="delivery")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="pct")
    direction = models.CharField(
        max_length=16, choices=DIRECTION_CHOICES, default="higher_is_better")
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default="manual")
    derived_metric = models.CharField(
        max_length=24, choices=DERIVED_METRIC_CHOICES, blank=True,
        help_text="Required when the source is derived; must be blank otherwise. The registry "
                  "is CLOSED — a key here is a promise that a reviewed resolver exists for it")
    weight = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Relative weight in the composite. Weights are re-weighted over the KPIs "
                  "actually scored")
    target_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    warning_threshold = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True)
    scoring_method = models.CharField(max_length=8, choices=SCORING_CHOICES, default="band")
    maps_to_dimension = models.CharField(
        max_length=16, choices=DIMENSION_CHOICES, blank=True,
        help_text="Which scm.SupplierScorecard column this KPI feeds. Blank = feeds none")
    applies_to = models.CharField(max_length=8, choices=APPLIES_CHOICES, default="all")
    applies_to_tier = models.CharField(
        max_length=16, choices=TIER_CHOICES, blank=True,
        help_text="Required when 'applies to' is one tier; matched against "
                  "scm.SupplierProfile.tier")
    review_frequency = models.CharField(
        max_length=12, choices=FREQUENCY_CHOICES, default="quarterly",
        help_text="The intended cadence. Stored only — nothing schedules off it yet; "
                  "scorecards are generated on demand")
    industry_benchmark_value = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Hand-entered reference figure — there is no external benchmark feed in "
                  "this system")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_supplier_kpis",
        help_text="The person answerable for this number")
    display_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(
        default=True,
        help_text="Retire a KPI by deactivating it — never delete it out from under measured "
                  "history")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["display_order", "code"]
        unique_together = (("tenant", "code"), ("tenant", "number"))
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="prc_skp_tnt_active_idx"),
            models.Index(fields=["tenant", "category"], name="prc_skp_tnt_cat_idx"),
            models.Index(fields=["tenant", "source"], name="prc_skp_tnt_source_idx"),
        ]
        verbose_name = "Supplier KPI"
        verbose_name_plural = "Supplier KPIs"

    def __str__(self):
        # ``code`` leads: it is the master identifier a score row is rolled up by, and the
        # string a reviewer reads on a scorecard line.
        return f"{self.code} · {self.name}"

    def clean(self):
        """Three conjunctions, collected so a form shows every problem at once, not the first.

        1. **Band ordering follows ``direction``.** Only the thresholds that are actually set
           take part, so a KPI with just a target and a critical line is still checked.
        2. **``source`` and ``derived_metric`` agree.** A derived KPI must name its metric; any
           other KPI must not carry one — a stale key on a manual KPI reads like a computation
           that is not happening.
        3. **``applies_to`` and ``applies_to_tier`` agree**, for the same reason.
        """
        super().clean()
        errors = {}

        # Rule 1 — band ordering by direction. Walk the set thresholds in their natural order
        # (target, warning, critical) and require each to be no "better" than its predecessor.
        bands = [(field, value) for field, value in (
            ("target_value", self.target_value),
            ("warning_threshold", self.warning_threshold),
            ("critical_threshold", self.critical_threshold),
        ) if value is not None]
        lower_is_better = self.direction == "lower_is_better"
        for (prev_field, prev_value), (field, value) in zip(bands, bands[1:]):
            if lower_is_better and value < prev_value:
                errors[field] = (
                    f"The {_BAND_LABELS[field]} must not be below the "
                    f"{_BAND_LABELS[prev_field]} for a lower-is-better KPI.")
            elif not lower_is_better and value > prev_value:
                errors[field] = (
                    f"The {_BAND_LABELS[field]} must not be above the "
                    f"{_BAND_LABELS[prev_field]} for a higher-is-better KPI.")

        # Rule 2 — the derived conjunction.
        if self.source == "derived" and not self.derived_metric:
            errors["derived_metric"] = "A derived KPI has to say which metric computes it."
        elif self.source != "derived" and self.derived_metric:
            errors["derived_metric"] = "Only a derived KPI carries a metric key — clear it."

        # Rule 3 — the tier conjunction.
        if self.applies_to == "tier" and not self.applies_to_tier:
            errors["applies_to_tier"] = "Say which tier this KPI applies to."
        elif self.applies_to == "all" and self.applies_to_tier:
            errors["applies_to_tier"] = (
                "This KPI applies to all suppliers — clear the tier.")

        if errors:
            raise ValidationError(errors)

    def score_and_band(self, measured_value):
        """``(Decimal | None, str)`` — the ONE scale. Pure: no queries, no writes, no clock.

        Generate, the manual score edit and the tests all band through this, so a figure can
        never mean one thing on a scorecard and another on a board.

        **Band** (independent of ``scoring_method``, and it uses only the thresholds that are
        set) — worse than critical is ``"critical"``, worse than warning is ``"warning"``,
        anything else is ``"ok"``. With NEITHER threshold set there is no line to fall on either
        side of, so the band is ``"unknown"`` rather than a flattering ``"ok"``.

        **Score** — ``direct`` clamps the value itself to 0-100; ``linear`` interpolates between
        the critical line (0) and the target (100); ``band`` reads the band table. ``linear``
        needs a target, a critical line and a non-zero span pointing the same way as
        ``direction``; when it does not have one it FALLS BACK to the band table. That fallback
        is deliberate and documented, not an error: a half-configured KPI should still band, and
        raising here would break generate for every supplier over one bad definition.

        A ``None`` measurement scores ``None`` and bands ``"unknown"`` — a missing measurement
        is not a zero, and writing one would quietly punish a supplier for a gap in OUR data.
        """
        if measured_value is None:
            return None, "unknown"

        value = Decimal(measured_value)
        warning = self.warning_threshold
        critical = self.critical_threshold
        lower_is_better = self.direction == "lower_is_better"

        if critical is not None and (value > critical if lower_is_better else value < critical):
            band = "critical"
        elif warning is not None and (value > warning if lower_is_better else value < warning):
            band = "warning"
        elif warning is not None or critical is not None:
            band = "ok"
        else:
            band = "unknown"

        score = None
        method = self.scoring_method
        if method == "direct":
            score = min(max(value, ZERO), _MAX_SCORE)
        elif method == "linear":
            target = self.target_value
            if target is not None and critical is not None:
                if not lower_is_better and target > critical:
                    score = _MAX_SCORE * (value - critical) / (target - critical)
                elif lower_is_better and critical > target:
                    score = _MAX_SCORE * (critical - value) / (critical - target)
                if score is not None:
                    score = min(max(score, ZERO), _MAX_SCORE)
        if score is None and method != "direct":
            # ``band`` scoring, and the documented ``linear`` fallback. ``None`` for an
            # unknown band — see the docstring.
            score = _BAND_SCORES.get(band)

        if score is not None:
            score = score.quantize(_SCORE_STEP)
        return score, band
