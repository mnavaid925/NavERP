"""Procurement 6.16 Supplier Performance & Evaluation — SupplierKpiScore.

**What it is.** One measured fact: this KPI, on this ``scm.SupplierScorecard``, came back at this
value, scored this, banded here. A child fact row (the ``KpiSnapshot`` /
``InvoiceMatchVariance`` precedent) — ``TenantOwned``, no ``number``, because nobody quotes a
score line by reference; they quote the scorecard it sits on.

**The columns ending ``_at_time`` are the point of this model.** ``weight_applied``,
``target_at_time``, ``direction_at_time``, ``source_at_time``, ``unit_at_time``, ``kpi_name`` and
``kpi_category`` are copied off the KPI at generation and never rewritten. Re-tune a KPI's weight
or move its target next quarter and every closed period still reads exactly as it read when the
supplier was shown it. A scorecard whose numbers change retroactively is a scorecard nobody can
be held to.

**``unique_together = (tenant, scorecard, kpi)`` is the safety on the Generate button.** Pressing
it twice UPDATES each line in place instead of doubling the scorecard — see
``apps.procurement.performance.generate_scorecard_lines``.

**Generating is a ONE-WAY DOOR, by design.** ``generate_scorecard_lines`` writes the four
``scm.SupplierScorecard`` dimension columns from these lines and sets that scorecard's
``manual_override``. ``scm.SupplierScorecard.recompute_from_signals()`` returns immediately on
any row carrying that flag, so from the first generate onwards SCM's signal engine leaves the
scorecard alone and 6.16 owns it. That is deliberate — two engines writing the same four columns
would fight, and the one with an auditable KPI line behind every figure should win — but it
cannot be undone from the 6.16 pages. The sentence the user is shown is
``performance.HANDOVER_NOTE``, and it appears on the evaluation register, on the evaluation
detail page and in the Generate button's confirm dialog.

**Two CRUD exemptions, documented so a reviewer reads intent rather than omission:**

1. **No create form and no ``supplierkpiscore_create`` route.** Lines are system-written by
   ``supplierevaluation_generate``; a hand-created line would be a measurement with no
   computation behind it (the ``SpendReportSnapshot`` / ``CostForecast``-has-no-edit precedent).
2. **Edit is limited to ``measured_value`` + ``comment``, and only when
   ``source_at_time == "manual"``. The VIEW is the gate** — any other row redirects to the detail
   page with a ``messages.error``. A disabled widget is UX, not an authorization boundary.
   **Delete (POST-only) DOES exist**, so a retired KPI's stale line can be removed.

**Import discipline.** This module imports the shared toolkit from
``apps.procurement.models._base`` and NOTHING else at module top. The cross-app read
(``scm.SupplierScorecard`` in ``clean()``) happens inside the method that needs it — the same
thing ``scm.SupplierScorecard.recompute_from_signals`` does with its own imports, and for the
same reason: both model packages pull the same ``_base``, and a module-level sibling import that
runs while ``apps.procurement.models`` is still initialising is exactly how an import cycle gets
shipped.
"""
from apps.procurement.models._base import *  # noqa: F401,F403

# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``apps.procurement.models`` — the package __init__ re-export block lands at Integrate.
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi


#: Where the measured value fell against the KPI's own thresholds. ``unknown`` is a real answer,
#: not a placeholder: a KPI with no thresholds set has no line to fall either side of, and a
#: measurement with no value has nothing to band at all.
BAND_CHOICES = [
    ("ok", "On target"), ("warning", "Warning"),
    ("critical", "Critical"), ("unknown", "Not banded"),
]

#: L33 — theme.css ships badge-green / -red / -amber / -info / -muted / -slate and NOTHING else.
#: badge-success / badge-warning / badge-danger DO NOT EXIST and render completely unstyled.
BAND_CSS = {
    "ok": "badge-green", "warning": "badge-amber",
    "critical": "badge-red", "unknown": "badge-muted",
}


class SupplierKpiScore(TenantOwned):
    """One KPI's measured figure on one scorecard, with the definition frozen beside it."""

    # Re-exported through the class so forms, views and templates reach them off the model,
    # mirroring SupplierKpi. The module-level names stay the definition; these are aliases.
    BAND_CHOICES = BAND_CHOICES
    BAND_CSS = BAND_CSS

    scorecard = models.ForeignKey(
        "scm.SupplierScorecard", on_delete=models.CASCADE,
        related_name="procurement_kpi_scores")
    kpi = models.ForeignKey(
        "procurement.SupplierKpi", on_delete=models.PROTECT, related_name="scores",
        help_text="PROTECT: deleting a KPI must never silently delete measured history — "
                  "retire it with is_active=False")
    measured_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))])
    weight_applied = models.PositiveSmallIntegerField(
        default=0,
        help_text="The KPI's weight FROZEN at generation — a later retune must not rewrite a "
                  "closed period")
    band = models.CharField(max_length=10, choices=BAND_CHOICES, default="unknown")

    # ---- Frozen-at-generation columns. editable=False: history, never input. ----------------
    target_at_time = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False)
    direction_at_time = models.CharField(max_length=16, blank=True, editable=False)
    source_at_time = models.CharField(max_length=8, blank=True, editable=False)
    unit_at_time = models.CharField(max_length=10, blank=True, editable=False)
    kpi_name = models.CharField(max_length=160, blank=True, editable=False)
    kpi_category = models.CharField(max_length=16, blank=True, editable=False)

    breakdown = models.JSONField(
        default=dict, blank=True, editable=False,
        help_text="How the figure was arrived at — numerator, denominator, window, rows "
                  "considered")
    respondent_count = models.PositiveIntegerField(
        default=0, editable=False,
        help_text="How many 360 responses were aggregated for a survey KPI")
    comment = models.TextField(blank=True)
    # default=timezone.now, NOT auto_now_add: a re-run must RE-STAMP freshness, and auto_now_add
    # would freeze this at the first generate and quietly claim a stale figure is current.
    computed_at = models.DateTimeField(default=timezone.now, editable=False)
    computed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="procurement_kpi_scores_computed")

    class Meta:
        # The DENORMALISED columns — grouping a register by category and name costs no JOIN.
        ordering = ["kpi_category", "kpi_name", "id"]
        # THIS is what makes generate safe to press twice.
        unique_together = ("tenant", "scorecard", "kpi")
        indexes = [
            models.Index(fields=["tenant", "scorecard"], name="prc_sks_tnt_scr_idx"),
            models.Index(fields=["tenant", "band"], name="prc_sks_tnt_band_idx"),
            models.Index(fields=["tenant", "kpi"], name="prc_sks_tnt_kpi_idx"),
            # The register's DEFAULT SORT, covered. Nothing above matches ``ordering``, so every
            # page of the score register was a filesort over the whole tenant partition:
            # measured 130 ms -> 1,484 ms at 60,041 lines with the query count FLAT at 12, and
            # ``EXPLAIN`` reporting ``Using where; Using filesort``. This is the fastest-growing
            # table in 6.16 (suppliers x periods x catalogue size) and it was the one ledger-like
            # model in the app without its sort indexed — 12 siblings already carry theirs.
            models.Index(fields=["tenant", "kpi_category", "kpi_name", "id"],
                         name="prc_sks_tnt_cat_name_idx"),
        ]
        verbose_name = "Supplier KPI Score"
        verbose_name_plural = "Supplier KPI Scores"

    def __str__(self):
        # The FROZEN name, not ``self.kpi.name``: a line printed in a list must not cost a JOIN,
        # and a KPI renamed since must not re-label a closed period.
        return f"{self.kpi_name or 'KPI'} · {self.score if self.score is not None else '—'}"

    def clean(self):
        """Same-tenant guards on both FKs.

        Resolved with ``_id`` guards plus an explicit queryset lookup, never
        ``self.scorecard.tenant_id`` — the two-arg ``getattr`` form raises
        ``RelatedObjectDoesNotExist`` on an unsaved instance whose FK was not set, which 500'd a
        live add page once already (the ``VendorSuspension.clean()`` precedent). Skipped
        entirely while ``tenant_id`` is unset: there is nothing to compare against yet, and the
        CRUD helpers stamp the tenant before ``full_clean()`` only via ``TenantUniqueMixin``.
        """
        super().clean()
        errors = {}

        if self.tenant_id and self.scorecard_id:
            # Cross-app read, local by design — see the module docstring.
            from apps.scm.models import SupplierScorecard
            if not SupplierScorecard.objects.filter(pk=self.scorecard_id,
                                                    tenant_id=self.tenant_id).exists():
                errors["scorecard"] = "That record belongs to another workspace."
        if self.tenant_id and self.kpi_id:
            if not SupplierKpi.objects.filter(pk=self.kpi_id,
                                              tenant_id=self.tenant_id).exists():
                errors["kpi"] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    @property
    def band_css(self):
        """The theme class for this line's band. Colour-named only (L33)."""
        return self.BAND_CSS.get(self.band, "badge-slate")

    @property
    def contribution(self):
        """``score × weight_applied``, or ``None`` when the line never scored.

        The numerator of the composite arithmetic the evaluation detail page shows: divide the
        sum of these by the sum of ``weight_applied`` over the SAME lines and you have the
        composite, which is why an unscored line contributes ``None`` rather than 0 — it must
        drop out of both sides, not drag the top one down.
        """
        if self.score is None:
            return None
        return self.score * self.weight_applied
