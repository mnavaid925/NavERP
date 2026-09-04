"""Procurement 6.17 Risk & Compliance Management — SupplierRiskSignal.

**NavERP.md bullet 2, "Supplier Financial Risk Monitoring".** One row per observation of one
financial-health metric for one supplier, from one provider, on one date.

**The inverted scales ARE the model.** A single stored "risk score" column would be a lie:
RapidRatings' FHR runs 1-100 where **100 is healthy**, while D&B's Supplier Evaluation Risk runs
1-9 where **9 is dangerous**. Storing both as "score" and sorting descending would rank the two
safest suppliers in the workspace next to each other at opposite ends of the register. So every
row carries its ``provider`` and its ``metric``, and :data:`METRIC_SCALES` — the single most
important constant in this sub-module — is what turns the raw number into a comparable
:attr:`SupplierRiskSignal.risk_position` (**0 = safest, 100 = riskiest**, always, whatever the
provider's convention).

**Derived, not typed.** ``scale_min``, ``scale_max``, ``higher_is_better``, ``risk_position``,
``band``, ``previous_value`` and ``trend`` are all ``editable=False`` and all stamped by
:meth:`SupplierRiskSignal.derive` inside ``save()``. An operator types the value and the date;
the interpretation is the system's, so two people entering the same D&B report cannot end up
with two different bands.

**Trend is compared on RISK POSITION, never on the raw value.** A SER falling from 7 to 4 is an
IMPROVEMENT; a raw-value comparison reads it as a fall and would report deterioration. This is
the one place the inversion has to be got right and it is why the comparison lives here rather
than in a view.

**Advisory, never blocking.** :attr:`SupplierRiskSignal.breaches_minimum` colours a badge against
:data:`MINIMUM_ACCEPTABLE` and stops nothing — no PO hold, no payment block, no award refusal
(the ``ReceiptTolerancePolicy`` posture). The only place a vendor is actually blocked is the 6.4
``VendorSuspension`` register.

**No second composite score.** ``scm.SupplierRiskAssessment`` (SCM 4.2) already owns the internal
four-factor composite. 6.17 CITES it on the detail page and links to the 4.2 register; it never
computes a rival headline (L29/L36/L37).

**Honesty about provenance.** There is no live bureau call anywhere in this repo. Every row is
captured by a person or from a CSV and states its ``captured_by``, ``observed_on`` and
``source_ref``. ``source_ref`` renders as TEXT and never as an ``href`` — it is a staff-typed
string, and the ``ProcurementAlert.link_url`` lesson applies.

**Decimal hygiene (L35).** ``Decimal("NaN")`` parses cleanly and then raises ``InvalidOperation``
on the first ``<``. Every value that reaches an ordering comparison goes through :func:`_finite`
FIRST, so a non-finite number degrades to "unrated" instead of 500ing.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.urls import NoReverseMatch, reverse

from apps.procurement.models._base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------------------------

#: Who published the observation. BitSight and EcoVadis are reserved deliberately: a later
#: connector writes the same rows with no migration and no second table.
PROVIDER_CHOICES = [
    ("dnb", "Dun & Bradstreet"),
    ("rapidratings", "RapidRatings"),
    ("creditsafe", "Creditsafe"),
    ("experian", "Experian"),
    ("coface", "Coface"),
    ("ecovadis", "EcoVadis"),
    ("bitsight", "BitSight"),
    ("internal", "Internal assessment"),
    ("other", "Other provider"),
]

#: WHICH number was observed. The label states the scale and its direction on purpose — the
#: direction is the thing an operator gets wrong, and it is the thing this model exists to fix.
METRIC_CHOICES = [
    ("fhr", "RapidRatings FHR (1-100, higher is healthier)"),
    ("ser_rating", "D&B Supplier Evaluation Risk (1-9, higher is riskier)"),
    ("paydex", "D&B PAYDEX (1-100, higher is prompter)"),
    ("failure_score", "D&B Failure / Insolvency score"),
    ("credit_score", "Credit score (1-100)"),
    ("credit_rating", "Credit rating notch (1-21)"),
    ("altman_z", "Altman Z-score"),
    ("dso_days", "Days sales outstanding"),
    ("days_beyond_terms", "Days beyond terms"),
    ("current_ratio", "Current ratio"),
    ("esg_rating", "ESG / sustainability rating"),
    ("cyber_rating", "Cyber security rating"),
    ("other", "Other metric"),
]

#: ``{metric: (scale_min, scale_max, higher_is_better)}`` — **the single most important constant
#: in this sub-module.**
#:
#: FHR 100 is healthy; SER 9 is dangerous; DSO 90 days is bad and DSO 10 days is good. Without
#: this table a "risk score" column cannot be compared across providers, ranked, or trended, and
#: a falling number is as likely to be good news as bad. With it, every observation collapses to
#: one comparable 0-100 :attr:`SupplierRiskSignal.risk_position` where 0 is always the safest.
#:
#: ``"other"`` maps to ``(None, None, True)`` and is not an oversight: an unregistered metric has
#: no scale, so it bands as ``"unrated"``. Saying "we do not know" is the honest answer; banding
#: it ``low`` by default would be a fabricated all-clear.
METRIC_SCALES = {
    "fhr": (Decimal("1"), Decimal("100"), True),
    "ser_rating": (Decimal("1"), Decimal("9"), False),
    "paydex": (Decimal("1"), Decimal("100"), True),
    "failure_score": (Decimal("1"), Decimal("100"), True),
    "credit_score": (Decimal("1"), Decimal("100"), True),
    "credit_rating": (Decimal("1"), Decimal("21"), True),
    "altman_z": (Decimal("-5"), Decimal("10"), True),
    "dso_days": (Decimal("0"), Decimal("180"), False),
    "days_beyond_terms": (Decimal("0"), Decimal("120"), False),
    "current_ratio": (Decimal("0"), Decimal("5"), True),
    "esg_rating": (Decimal("0"), Decimal("100"), True),
    "cyber_rating": (Decimal("250"), Decimal("900"), True),
    "other": (None, None, True),
}

#: The escalation ladder, read off the 0-100 risk position.
BAND_CHOICES = [
    ("low", "Low"),
    ("watch", "Watch"),
    ("elevated", "Elevated"),
    ("critical", "Critical"),
    ("unrated", "Not banded"),
]

#: theme.css ships ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33). A semantic badge-success / badge-danger renders completely unstyled and
#: passes every test, so every mapping lives here rather than in template {% if %} ladders.
BAND_CSS = {
    "low": "badge-green",
    "watch": "badge-info",
    "elevated": "badge-amber",
    "critical": "badge-red",
    "unrated": "badge-muted",
}

#: Half-open ceilings on the RISK POSITION (0 = safest): ``< 25 low``, ``< 50 watch``,
#: ``< 75 elevated``, anything at or above 75 is ``critical``.
BAND_THRESHOLDS = (
    (Decimal("25"), "low"),
    (Decimal("50"), "watch"),
    (Decimal("75"), "elevated"),
)

TREND_CHOICES = [
    ("new", "First observation"),
    ("improved", "Improved"),
    ("stable", "Stable"),
    ("deteriorated", "Deteriorated"),
]
TREND_CSS = {
    "new": "badge-slate",
    "improved": "badge-green",
    "stable": "badge-muted",
    "deteriorated": "badge-red",
}

#: What a HUMAN did about the observation. Moved by the three verbs only, never by a form.
REVIEW_STATUS_CHOICES = [
    ("new", "New"),
    ("reviewed", "Reviewed"),
    ("actioned", "Actioned"),
    ("dismissed", "Dismissed"),
]
REVIEW_CSS = {
    "new": "badge-red",
    "reviewed": "badge-amber",
    "actioned": "badge-green",
    "dismissed": "badge-muted",
}

#: Still needs a human. ``new`` is red because unreviewed means unattended.
OPEN_REVIEW_STATUSES = ("new", "reviewed")

#: Closed out. A signal that has been actioned or dismissed is not re-opened — capture the next
#: observation instead, which is what leaves an honest series.
TERMINAL_REVIEW_STATUSES = ("actioned", "dismissed")

#: Buyer-imposed floors. **ADVISORY ONLY** — this colours a badge and blocks nothing (research
#: 2.7; the ``ReceiptTolerancePolicy`` posture). D&B buyers commonly impose a maximum acceptable
#: SER; RapidRatings' 40 is the line below which a supplier is treated as financially distressed.
MINIMUM_ACCEPTABLE = {
    "ser_rating": Decimal("5"),
    "fhr": Decimal("40"),
}

#: How much the risk position has to move before it counts as movement rather than noise.
TREND_EPSILON = Decimal("0.50")

#: An observation older than this is stale whatever its refresh date says.
STALE_AFTER_DAYS = 180

#: How many observations the detail page's series shows.
SERIES_LIMIT = 12

#: A deterioration only raises a 6.1 alert once it lands in one of these bands — a wobble inside
#: ``low``/``watch`` is a data point, not an inbox item.
ALERT_BANDS = ("elevated", "critical")

#: The ``ProcurementAlert.kind`` this model raises.
#:
#: **HAND-OFF (Integrate step):** ``ProcurementAlert.KIND_CHOICES`` does not carry
#: ``("risk", "Risk")`` yet, and ``kind_css`` has no ``"risk"`` entry. Both are ONE surgical Edit
#: to ``apps/procurement/models/DashboardPortal/ProcurementAlerts.py`` plus an ``AlterField`` in
#: the 6.17 migration (precedent: ``0012_alter_procurementalert_kind`` did exactly this for 6.8's
#: ``"contract"``). That file is shared with three concurrently-building sub-modules, so this
#: entity does not touch it. Until it lands the write still succeeds — ``max_length=12`` fits,
#: Django does not enforce CHOICES on ``save()`` — and the alert renders with a ``badge-slate``
#: kind chip instead of a red one. Nothing crashes; the chip is simply the wrong colour.
ALERT_KIND = "risk"

#: Ceiling of the ``value`` column's shape, ``DecimalField(max_digits=12, decimal_places=2)``.
#: Bound-checked in ``clean()`` so an oversized number is a friendly field error rather than a
#: driver ``DataError`` from inside ``save()``.
MAX_VALUE = Decimal("9999999999.99")

_HUNDRED = Decimal("100")
_CENT = Decimal("0.01")

#: The columns :meth:`SupplierRiskSignal.derive` reads. A ``save(update_fields=…)`` that touches
#: none of them — every review verb, and the alert stamp — skips the whole derivation, including
#: its prior-row query.
_DERIVATION_INPUTS = frozenset({"party", "party_id", "provider", "metric", "observed_on", "value"})


def _finite(value):
    """``value`` as a Decimal that is safe to ORDER, or ``None``.

    L35, the whole of it: ``Decimal("NaN")`` parses without complaint and then raises
    ``InvalidOperation`` on the first ``<`` — an unhandled 500 from a number that looked fine
    going in. ``Decimal("Infinity")`` compares fine and then blows the column width. Both are
    refused HERE, once, before any comparison or arithmetic happens, so every caller downstream
    can assume ordering is safe.
    """
    if value is None:
        return None
    try:
        value = Decimal(value)
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        return None
    return value if value.is_finite() else None


def _classify(risk_delta):
    """A signed RISK delta -> a trend value. Positive means risk went UP, which is deterioration.

    Both callers hand this a delta already expressed in the risk direction, so the inversion is
    resolved exactly once, at the call site that knows the metric's convention.
    """
    if risk_delta > TREND_EPSILON:
        return "deteriorated"
    if risk_delta < -TREND_EPSILON:
        return "improved"
    return "stable"


def alert_link(pk):
    """The internal path a raised risk alert points at.

    ``reverse()`` first, because a hardcoded string silently breaks the day the route moves. The
    literal fallback exists because this sub-module's URLconf is not spliced into
    ``apps/procurement/urls/__init__.py`` until the Integrate step, and a seeder run before then
    would otherwise die on ``NoReverseMatch``. Both produce the same string — the app is mounted
    at ``procurement/`` and this entity claims the ``risk-signals/`` segment — so an alert raised
    before integration dedupes correctly against one raised after.

    WARNING: ``ProcurementAlert.clean()`` requires a single-slash internal path; an absolute or
    scheme-relative value here would turn the alert card into an open redirect.
    """
    try:
        return reverse("procurement:risksignal_detail", args=[pk])
    except NoReverseMatch:
        return f"/procurement/risk-signals/{pk}/"


class SupplierRiskSignal(TenantNumbered):
    """One observation of one financial-health metric for one supplier, on one date."""

    NUMBER_PREFIX = "SRS"

    # Re-exposed on the class so views, templates and tests reach the vocabulary through the
    # model rather than importing the module constants a second time.
    PROVIDER_CHOICES = PROVIDER_CHOICES
    METRIC_CHOICES = METRIC_CHOICES
    METRIC_SCALES = METRIC_SCALES
    BAND_CHOICES = BAND_CHOICES
    BAND_CSS = BAND_CSS
    BAND_THRESHOLDS = BAND_THRESHOLDS
    TREND_CHOICES = TREND_CHOICES
    TREND_CSS = TREND_CSS
    REVIEW_STATUS_CHOICES = REVIEW_STATUS_CHOICES
    REVIEW_CSS = REVIEW_CSS
    OPEN_REVIEW_STATUSES = OPEN_REVIEW_STATUSES
    TERMINAL_REVIEW_STATUSES = TERMINAL_REVIEW_STATUSES
    MINIMUM_ACCEPTABLE = MINIMUM_ACCEPTABLE
    TREND_EPSILON = TREND_EPSILON
    STALE_AFTER_DAYS = STALE_AFTER_DAYS
    SERIES_LIMIT = SERIES_LIMIT
    ALERT_BANDS = ALERT_BANDS
    ALERT_KIND = ALERT_KIND
    MAX_VALUE = MAX_VALUE

    # PROTECT: deleting a party that carries a monitoring series would erase the evidence that
    # its financial health was ever watched. The party must be dealt with, not orphaned.
    party = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="procurement_risk_signals",
        help_text="The supplier this observation is about")
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default="internal",
                                help_text="Who published the number")
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES, default="other",
                              help_text="Which number — the scale and its direction come from it")
    observed_on = models.DateField(
        default=timezone.localdate,
        help_text="The date the PROVIDER measured it, which is not the date it was captured here")
    value = models.DecimalField(max_digits=12, decimal_places=2,
                                help_text="The raw number exactly as the provider published it")

    # -- DERIVED. Every one of these is stamped by derive(); none is ever operator-supplied. ----
    scale_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                    editable=False)
    scale_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                    editable=False)
    higher_is_better = models.BooleanField(default=True, editable=False)
    risk_position = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, editable=False,
        help_text="Normalised 0.00-100.00 where 0 is the SAFEST end of this metric's own scale")
    band = models.CharField(max_length=12, choices=BAND_CHOICES, default="unrated",
                            editable=False)
    previous_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                         editable=False)
    trend = models.CharField(max_length=14, choices=TREND_CHOICES, default="new", editable=False)

    # -- the human column. Moved by the three verbs only. --------------------------------------
    review_status = models.CharField(max_length=12, choices=REVIEW_STATUS_CHOICES, default="new",
                                     editable=False)
    review_note = models.TextField(blank=True, editable=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_risk_signals_reviewed", editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)

    next_refresh_on = models.DateField(
        null=True, blank=True,
        help_text="When this supplier is due a fresh observation of this metric")
    # Rendered as TEXT, never as an href — a staff-typed string does not become a link.
    source_ref = models.CharField(
        max_length=160, blank=True,
        help_text="The provider's report / reference id, so the observation can be traced back")
    evidence = models.ForeignKey(
        "core.Document", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_risk_signals",
        help_text="The saved report or extract this observation rests on")
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_risk_signals_captured", editable=False)
    # Stamped by raise_deterioration_alert(); the reverse accessor is what makes the party+metric
    # idempotency check possible without a second dedupe column.
    alert = models.ForeignKey(
        "procurement.ProcurementAlert", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="risk_signals", editable=False,
        help_text="The 6.1 alert this deterioration raised, if any")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-observed_on", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "party", "observed_on"],
                         name="prc_srs_tnt_party_obs_idx"),
            models.Index(fields=["tenant", "band"], name="prc_srs_tnt_band_idx"),
            models.Index(fields=["tenant", "review_status"], name="prc_srs_tnt_review_idx"),
            models.Index(fields=["tenant", "next_refresh_on"], name="prc_srs_tnt_refresh_idx"),
            # Backs BOTH the prior-row lookup in derive() and the detail page's series window.
            models.Index(fields=["tenant", "party", "provider", "metric", "observed_on"],
                         name="prc_srs_series_idx"),
        ]
        verbose_name = "Supplier Risk Signal"
        verbose_name_plural = "Supplier Risk Signals"

    def __str__(self):
        # Guarded on the id: on an UNSAVED instance (a ModelForm re-rendering its own errors)
        # ``self.party`` raises RelatedObjectDoesNotExist, and a validation page must never 500.
        party = self.party if self.party_id else "-"
        return f"{self.number or 'SRS'} · {party} · {self.get_metric_display()} {self.value}"

    # -- the scale ------------------------------------------------------------------------------

    @property
    def scale(self):
        """``(scale_min, scale_max, higher_is_better)`` for this row's metric.

        Read from :data:`METRIC_SCALES` rather than from the three stored columns, so it is
        already correct on an UNSAVED instance — a form re-rendering its own errors, or a preview.
        :meth:`derive` stamps those columns from this same tuple, so a saved row's columns and
        this property can never disagree.
        """
        return METRIC_SCALES.get(self.metric, (None, None, True))

    @property
    def has_scale(self):
        """Whether this metric has a registered scale at all (``metric="other"`` does not)."""
        scale_min, scale_max, _ = self.scale
        return scale_min is not None and scale_max is not None

    @property
    def is_banded(self):
        """Whether ``risk_position``/``band`` mean anything for this row.

        Templates gate every reference to the position bar on this rather than on
        ``risk_position``: the Django template language has no ``None`` literal, so
        ``{% if obj.risk_position %}`` would ALSO hide a perfectly valid position of 0.00 — the
        safest possible supplier, rendered blank.
        """
        return self.risk_position is not None

    # -- derivation ------------------------------------------------------------------------------

    def derive(self):
        """Stamp every DERIVED column from :data:`METRIC_SCALES` and the prior observation.

        Idempotent, and the ONLY writer of the seven derived columns. Runs inside ``save()``
        before the row is written, in the order the plan pins: scale, position, band, then trend
        (which needs the position the two steps above just produced).
        """
        self.scale_min, self.scale_max, self.higher_is_better = self.scale
        self.risk_position = self._derive_risk_position()
        self.band = self._derive_band()
        self._derive_trend()

    def _derive_risk_position(self):
        """The raw value as a 0.00-100.00 risk position, 0 = safest. ``None`` when unscaled.

        This is where the inversion happens and it happens exactly once. Values outside the
        registered scale are CLAMPED to it rather than extrapolated: a PAYDEX of 140 is a typo or
        a rescaled feed, and either way it is not 140% of the way along a 1-100 scale.
        """
        value = _finite(self.value)
        scale_min, scale_max, higher_is_better = self.scale
        if value is None or scale_min is None or scale_max is None:
            return None
        if scale_max <= scale_min:
            # A degenerate scale has no interior to position anything in. Not reachable from the
            # table as written; guarded so a future edit to it cannot divide by zero.
            return None
        clamped = min(max(value, scale_min), scale_max)
        position = (clamped - scale_min) / (scale_max - scale_min) * _HUNDRED
        if higher_is_better:
            # FHR 100 and PAYDEX 80 sit at the TOP of their scales and are the SAFEST readings,
            # so the position has to be flipped. SER 9 and DSO 90 do not.
            position = _HUNDRED - position
        return position.quantize(_CENT)

    def _derive_band(self):
        """The escalation band, read off the risk position. ``unrated`` when there is none."""
        position = self.risk_position
        if position is None:
            return "unrated"
        for ceiling, band in BAND_THRESHOLDS:
            if position < ceiling:
                return band
        return "critical"

    def _derive_trend(self):
        """Stamp ``previous_value`` and ``trend`` against the preceding observation."""
        prior = self.prior_observation()
        if prior is None:
            self.previous_value = None
            self.trend = "new"
            return
        self.previous_value = prior.value
        self.trend = self._compare_with(prior)

    def prior_observation(self):
        """The preceding observation in this row's own series, or ``None``.

        Same ``(tenant, party, provider, metric)``, on or before this row's ``observed_on``,
        newest first — ONE query, backed by ``prc_srs_series_idx``. Comparing across providers or
        across metrics would be meaningless, which is why all four are in the key.
        """
        if not (self.tenant_id and self.party_id and self.observed_on):
            return None
        qs = type(self).objects.filter(
            tenant_id=self.tenant_id, party_id=self.party_id, provider=self.provider,
            metric=self.metric, observed_on__lte=self.observed_on)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.order_by("-observed_on", "-id").first()

    def _compare_with(self, prior):
        """``improved`` / ``stable`` / ``deteriorated``, judged on RISK POSITION.

        **This is the entire point of the inverted scales.** A D&B SER moving 7 -> 4 is an
        IMPROVEMENT and an FHR moving 70 -> 40 is a DETERIORATION, even though both raw numbers
        fell. Comparing raw values would call the first one deterioration and the second one
        improvement — exactly backwards on one of them, whichever convention you picked.

        The fallback path exists for a pair where the metric HAS a registered scale but one side
        carries no stored position — a row written before the scale was registered, or one whose
        value was non-finite. It re-derives the same risk-direction delta from the raw values by
        hand and classifies it identically.

        An UNSCALED metric (``metric="other"``) never reaches that fallback and is always
        ``stable``. Its ``higher_is_better`` is the ``(None, None, True)`` placeholder that gives
        the COLUMN a default — it is not a claim that higher is better, and using it to judge a
        direction would invent one. For a number nobody registered a scale for, "we do not know
        which way is up" is the only honest answer, and reporting no movement is how this model
        says it. That is the same reasoning that bands ``other`` as ``unrated`` rather than
        ``low``.
        """
        here, there = _finite(self.risk_position), _finite(prior.risk_position)
        if here is not None and there is not None:
            return _classify(here - there)

        if not self.has_scale:
            return "stable"
        here, there = _finite(self.value), _finite(prior.value)
        if here is None or there is None:
            return "stable"
        # Express the raw movement in the RISK direction, then classify it identically.
        _, _, higher_is_better = self.scale
        risk_delta = (there - here) if higher_is_better else (here - there)
        return _classify(risk_delta)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or _DERIVATION_INPUTS.intersection(update_fields):
            self.derive()
        return super().save(*args, **kwargs)

    # -- derived display ---------------------------------------------------------------------

    @property
    def band_css(self):
        return BAND_CSS.get(self.band, "badge-muted")

    @property
    def trend_css(self):
        return TREND_CSS.get(self.trend, "badge-muted")

    @property
    def review_css(self):
        return REVIEW_CSS.get(self.review_status, "badge-muted")

    @property
    def minimum_acceptable(self):
        """The buyer-imposed floor for this metric, or ``None``. Advisory; see below."""
        return MINIMUM_ACCEPTABLE.get(self.metric)

    @property
    def breaches_minimum(self):
        """Whether this observation sits on the wrong side of its buyer-imposed floor.

        **ADVISORY ONLY.** It colours a badge and nothing else — it holds no PO, blocks no
        payment and refuses no award (research 2.7, the ``ReceiptTolerancePolicy`` posture). A
        hard stop belongs in the 6.4 suspension register, which is the one place a vendor is
        actually blocked.

        The direction is read from :data:`METRIC_SCALES`, not from a hardcoded ``<``: a floor of
        40 on FHR means "below 40 is bad" while a floor of 5 on SER means "above 5 is bad", and
        the same comparison operator cannot be right for both.
        """
        limit = MINIMUM_ACCEPTABLE.get(self.metric)
        value = _finite(self.value)
        if limit is None or value is None:
            return False
        _, _, higher_is_better = self.scale
        return value < limit if higher_is_better else value > limit

    @property
    def is_stale(self):
        """Whether the observation itself is older than :data:`STALE_AFTER_DAYS`."""
        if not self.observed_on:
            return False
        return (timezone.localdate() - self.observed_on).days > STALE_AFTER_DAYS

    @property
    def is_open(self):
        """Still awaiting a human — the only state in which this row may be amended."""
        return self.review_status in OPEN_REVIEW_STATUSES

    @property
    def is_terminal(self):
        """Actioned or dismissed. Closed out: no edit, no delete, no re-open."""
        return self.review_status in TERMINAL_REVIEW_STATUSES

    @property
    def alerts_on_deterioration(self):
        """Whether this row meets the band+trend bar an alert is raised at.

        Exposed so the detail page can explain why no alert was raised without re-deriving the
        rule (and getting it subtly different).
        """
        return self.trend == "deteriorated" and self.band in ALERT_BANDS

    # -- the three review verbs ------------------------------------------------------------------
    #
    # Each returns a bool and re-checks its own guard, so a direct POST is exactly as safe as a
    # click. None of them writes to the spine or to apps.accounting (L29): a signal records what
    # was observed and what a human decided about it, and stops nothing by itself.

    @staticmethod
    def _actor(user):
        """The user to stamp, or ``None`` for an anonymous / absent one."""
        return user if getattr(user, "is_authenticated", False) else None

    def _stamp_review(self, status, user, note):
        self.review_status = status
        self.review_note = note
        self.reviewed_by = self._actor(user)
        self.reviewed_at = timezone.now()
        self.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at",
                                 "updated_at"])
        return True

    def mark_reviewed(self, user, note=""):
        """Acknowledge the observation. From ``new`` only; the note is optional."""
        if self.review_status != "new":
            return False
        return self._stamp_review("reviewed", user, (note or "").strip())

    def mark_actioned(self, user, note):
        """Record that something was DONE about it. Note required — what was done is the point."""
        if self.is_terminal:
            return False
        note = (note or "").strip()
        if not note:
            return False
        return self._stamp_review("actioned", user, note)

    def dismiss(self, user, note):
        """Record that no action is needed. Note required.

        A dismissal with no stated reasoning is indistinguishable from a signal nobody looked at,
        which is precisely the finding an audit writes up.
        """
        if self.is_terminal:
            return False
        note = (note or "").strip()
        if not note:
            return False
        return self._stamp_review("dismissed", user, note)

    # -- the 6.1 alert -----------------------------------------------------------------------------

    def raise_deterioration_alert(self, user=None):
        """Raise ONE 6.1 ``ProcurementAlert`` for a deterioration, or return ``None``.

        **Called by the create/edit VIEW after a successful save, deliberately NOT from
        ``save()``.** A table write hidden inside ``save()`` fires in every seeder run and every
        test fixture, and an inbox that fills itself from a fixture is an inbox nobody reads.

        Idempotent by construction, exactly like ``run_renewal_alerts`` and
        ``Backorder.raise_alert``. Four guards, all four required:

        1. the trend is ``deteriorated`` — an improvement is not news,
        2. the band is ``elevated`` or ``critical`` — a wobble inside ``low`` is a data point,
        3. this row has not already stamped one, and
        4. no OPEN alert already exists for the same party + metric. That check rides the
           ``alert`` FK's reverse accessor, so it needs no dedupe column: a supplier whose FHR
           deteriorates three months running gets one inbox item, not three.
        """
        from apps.procurement.models.DashboardPortal.ProcurementAlerts import ProcurementAlert

        if not self.alerts_on_deterioration:
            return None
        if self.alert_id is not None:
            return None
        if not (self.pk and self.tenant_id and self.party_id):
            return None
        if ProcurementAlert.objects.filter(
                tenant_id=self.tenant_id, kind=ALERT_KIND,
                status__in=ProcurementAlert.OPEN_STATUSES,
                risk_signals__party_id=self.party_id,
                risk_signals__metric=self.metric).exists():
            return None

        # Width-guarded: ProcurementAlert.title is 200 chars, a Party name can be long and the
        # metric labels deliberately carry their scale ("D&B Supplier Evaluation Risk (1-9, higher
        # is riskier)"). Truncating the PARTS keeps the sentence readable; the final slice is the
        # belt-and-braces that guarantees the column width whatever the inputs were.
        party_name = str(self.party)[:60]
        metric_label = self.get_metric_display()[:70]
        title = f"{party_name} — {metric_label} deteriorated to {self.get_band_display()}"

        previous = self.previous_value
        message = (
            f"{metric_label} moved from {previous} to {self.value} "
            f"(observed {self.observed_on:%d %b %Y}, {self.get_provider_display()}). "
            f"Risk position {self.risk_position}/100 — {self.get_band_display().lower()} band. "
            f"Review the signal and decide: action it, or dismiss it with a reason.")

        alert = ProcurementAlert.objects.create(
            tenant_id=self.tenant_id,
            kind=ALERT_KIND,
            severity="critical" if self.band == "critical" else "warning",
            status="open",
            title=title[:200],
            message=message,
            link_url=alert_link(self.pk),
            created_by=self._actor(user),
        )
        self.alert = alert
        self.save(update_fields=["alert", "updated_at"])
        return alert

    # -- hygiene ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        # Cross-tenant guard on every FK. A narrowed <select> is UX; this is the model-level
        # backstop behind the form's own re-check, and it covers ``alert`` too — that one is
        # editable=False, so a form never offers it, but raise_deterioration_alert() sets it.
        if tenant_id:
            for field in ("party", "evidence", "alert"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        # L35: check finiteness BEFORE the magnitude comparison. Decimal("NaN") passes an
        # `is None` test and then raises InvalidOperation on the `>` below.
        if self.value is not None:
            value = _finite(self.value)
            if value is None:
                errors["value"] = "Enter a real number — not NaN or infinity."
            elif abs(value) > MAX_VALUE:
                errors["value"] = (
                    f"That is outside the range this field stores (±{MAX_VALUE}). "
                    f"Check the number against the provider's report.")

        if self.observed_on and self.observed_on > timezone.localdate():
            errors["observed_on"] = "A provider cannot have measured this in the future."

        if (self.next_refresh_on and self.observed_on
                and self.next_refresh_on < self.observed_on):
            errors["next_refresh_on"] = "The refresh date cannot be before the observation."

        if errors:
            raise ValidationError(errors)
