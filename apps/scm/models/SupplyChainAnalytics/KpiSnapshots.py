"""SCM 4.11 Supply Chain Analytics — ``KpiSnapshot``, the frozen period value behind every trend.

One row = one metric, measured over one period, at one dimension (or the roll-up ``""``), **as it
stood at capture**. The trend line, the sparkline on a tile and the period-over-period arrow all read
these rows; nothing re-computes history on render.

Why this is STORED rather than re-derived — THREE INDEPENDENT REASONS
---------------------------------------------------------------------
Any one of them would settle it; together they close the question.

1. **History drifts, so re-deriving silently rewrites the past.** ``Item.average_cost`` is rolled
   forward on every receipt (``Item.apply_receipt``, ``InventoryManagement/Items.py``), and a
   back-dated ``StockMove`` / goods receipt is a legal, routine correction in 4.1 and 4.3 — 4.10's
   returns post into the same ledger too. Re-running *last quarter's* turnover next month therefore
   returns a **different number for the same closed quarter**, with nothing on screen to say so. A
   trend is only worth reading if each point is frozen: otherwise "we improved" can be an artifact
   of a cost roll rather than of anything that happened in a warehouse.
2. **Cost.** Nearly every inventory metric here walks the append-only ``StockMove`` ledger to
   rebuild FIFO cost layers. Rendered live, a 12-period trend is **12 full ledger walks per page
   load, per tile**. Frozen, the same trend is one indexed read on
   ``(tenant, kpi_target, period_end)``.
3. **Every surveyed product ships it.** Sievo sells the refresh cycle itself as a feature, Oracle
   trends its KPI cards off stored history, and the in-repo precedent is CRM 1.6's
   ``ReportSnapshot`` — the same "frozen run of a computed thing" model, for the same reasons.

NO ``ModelForm`` — a DECISION, not an omission
----------------------------------------------
This model is **system-written**. There is deliberately no ``KpiSnapshots.py`` in ``apps/scm/forms``
and no create/edit view, which is a documented exception to the CRUD-completeness rule (the
``ReportSnapshot`` precedent):

* the **create path** is the ``kpisnapshot_capture`` POST action, which calls the capture service in
  ``apps/scm/analytics.py`` — a snapshot is only ever the output of ``compute_metric()``;
* shipped **CRUD is list + detail + delete** (POST-only), and delete exists because a bad capture run
  is the one thing a human legitimately needs to undo;
* a hand-typed ``value`` would be a *fabricated measurement* wearing the same badge as a computed
  one, which destroys the only property this table has — that its numbers were really measured.

A re-run is IDEMPOTENT, not additive
------------------------------------
``unique_together ("tenant", "kpi_target", "period_start", "dimension_key")`` means re-capturing a
period **updates** its row instead of stacking a second one, so the capture action is safe to press
twice. Two consequences follow and are load-bearing:

* ``computed_at`` is ``default=timezone.now``, **not** ``auto_now_add`` — a re-run must re-stamp
  freshness ("this figure is 3 minutes old"), and ``auto_now_add`` would freeze the *first* run's
  time forever and quietly lie about it ever after;
* ``dimension_key`` is ``blank=True`` and **never** ``null=True``. The roll-up row stores ``""``,
  which a unique index treats as a value; ``NULL``\\ s compare distinct, so a nullable column would
  let the roll-up duplicate on every single re-run — exactly the bug the constraint is here to stop.
"""
from apps.scm.models._base import *  # noqa: F401,F403

from apps.scm.models.SupplyChainAnalytics._choices import (
    BAND_CHOICES,
    METRIC_CHOICES,
    METRIC_LABELS,
    METRIC_META,
)


def format_metric_value(value, unit):
    """Render a raw metric ``Decimal`` the way its ``METRIC_UNIT_CHOICES`` unit wants to be read.

    Kept as a module-level function, not a method, because the **live** surfaces need it too: a KPI
    tile computed on the fly has no ``KpiSnapshot`` row to ask. ``apps/scm/analytics.py`` may import
    this directly (``analytics`` -> ``models`` is the legal direction) so a stored figure and the
    live figure it will become are formatted by the *same* code and cannot disagree.

    Money carries no currency symbol — SCM renders amounts as bare numbers everywhere else
    (``floatformat:2`` in the 4.1-4.10 templates) and the tenant's currency is not this model's to
    assume. Formatting is done on the ``Decimal`` itself, never via ``float()``.
    """
    if value is None:
        return "—"
    amount = Decimal(value)
    if unit == "money":
        return "{:,.2f}".format(amount)
    if unit == "pct":
        return "{:,.1f}%".format(amount)
    if unit == "days":
        return "{:,.1f} days".format(amount)
    if unit == "hours":
        return "{:,.1f} h".format(amount)
    if unit == "turns":
        return "{:,.2f} turns".format(amount)
    if unit == "count":
        return "{:,.0f}".format(amount)
    if unit == "score":
        return "{:,.1f}".format(amount)
    return "{:,.2f}".format(amount)  # unit retired from the catalog — still render the number


class KpiSnapshot(TenantOwned):
    """One frozen measurement of a :class:`KpiTarget`'s metric, for one period and one dimension.

    ``TenantOwned``, **not** ``TenantNumbered``: this is a child fact row, exactly like
    ``DashboardWidget`` / ``ReportSnapshot``. A per-tenant ``KPS-00001`` would be a number nobody
    ever quotes, on a table that grows by one row per target per dimension per period.

    See the module docstring for the three reasons it is stored, and for why it deliberately has no
    ``ModelForm``.
    """

    #: Band -> the theme.css badge class. **The classes are COLOUR-named** (``badge-green`` /
    #: ``badge-red`` / ``badge-amber`` / ``badge-muted``); ``badge-success`` / ``-warning`` /
    #: ``-danger`` DO NOT EXIST in ``static/css/theme.css`` and render as an unstyled grey pill with
    #: no error anywhere (lessons L33, four recurrences). Mapping it here once means no template has
    #: to invent one, and the live tiles can read ``KpiSnapshot.BAND_CSS`` for a band that has no
    #: row behind it yet.
    BAND_CSS = {
        "ok": "badge-green",
        "warning": "badge-amber",
        "critical": "badge-red",
        "unknown": "badge-muted",
    }

    kpi_target = models.ForeignKey("scm.KpiTarget", on_delete=models.CASCADE, related_name="snapshots")
    # Denormalized from the target. The point is the EDIT path, not the delete path: `kpi_target` is
    # CASCADE, so a deleted target takes its snapshots with it — but a target REPOINTED at another
    # metric must not silently relabel the numbers already captured under the old one. (Hence no
    # `clean()` asserting equality with `kpi_target.metric`: after a legitimate repoint the two
    # differ on purpose. The capture service stamps the target's OWN metric, and with no ModelForm
    # a caller-supplied metric is not a reachable input.)
    metric = models.CharField(max_length=40, choices=METRIC_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    dimension_key = models.CharField(
        max_length=64, blank=True,
        # No angle brackets in help_text on purpose: Django renders help_text through |safe, so a
        # literal "vendor:<pk>" would be parsed as an unknown HTML tag and vanish off the page.
        help_text="Blank = the roll-up; otherwise vendor:PK / carrier:PK / item:PK / "
                  "category:PK / location:PK")
    # Frozen at capture, so a renamed — or deleted — vendor cannot rewrite the labels on a trend
    # that was measured while it still had its old name.
    dimension_label = models.CharField(max_length=160, blank=True)
    # Written through q4() BY THE CAPTURE SERVICE. Deliberately NOT clamped in save(): the service
    # writes in bulk (bulk_create / bulk_update), which bypasses save() entirely, so a save()
    # override would guard only the path that was never the risk while reading as though it covered
    # both. The real requirement is that every writer passes through q4() — an over-range Decimal
    # raises DataError INSIDE bulk_update and fails the whole batch, not the one offending row.
    value = models.DecimalField(max_digits=16, decimal_places=4)
    target_value_at_time = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="What the target said at capture time — a later retune must not rewrite history")
    status_band = models.CharField(max_length=8, choices=BAND_CHOICES, default="unknown")
    # The component arithmetic behind `value`: SupplierScorecard.signal_summary's idea in structured
    # form. This is what makes a composite (e.g. the supplier disruption score) EXPLAINABLE — the
    # page renders the parts that produced the number instead of asking anyone to trust it. Every
    # value must be JSON-serializable, which is the contract analytics.compute_metric() returns.
    breakdown = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(default=timezone.now, editable=False)
    computed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="scm_kpi_snapshots")

    class Meta:
        ordering = ["-period_end", "metric", "dimension_key"]
        # Idempotency, not decoration — see the module docstring. A re-run UPDATES the period.
        unique_together = ("tenant", "kpi_target", "period_start", "dimension_key")
        indexes = [
            # The five report pages read a metric's history across targets.
            models.Index(fields=["tenant", "metric", "period_end"], name="scm_kps_tnt_met_end_idx"),
            # One tile's trend line — the hottest query in 4.11.
            models.Index(fields=["tenant", "kpi_target", "period_end"], name="scm_kps_tnt_tgt_end_idx"),
            # The list filter, and the control tower's "what is off target" count.
            models.Index(fields=["tenant", "status_band"], name="scm_kps_tnt_band_idx"),
        ]

    def __str__(self):
        period = self.period_end.strftime("%Y-%m-%d") if self.period_end else "unscheduled"
        return f"{self.metric_label} · {self.dimension_display} · {period}"

    def clean(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError({"period_end": "The period cannot end before it starts."})

    @property
    def metric_label(self):
        """The metric's human name, from the catalog. Falls back to the stored key so a snapshot of
        a metric later dropped from ``METRIC_META`` still renders as *something* readable rather
        than blank."""
        return METRIC_LABELS.get(self.metric, self.metric)

    @property
    def display(self):
        """``value`` formatted for its metric's unit — ``12.30 turns``, ``92.5%``, ``1,204.00``.

        Templates render ``{{ obj.display }}`` and never re-decide the unit, so a figure reads
        identically on the tile, in the list, on the detail page and in an export."""
        meta = METRIC_META.get(self.metric) or {}
        return format_metric_value(self.value, meta.get("unit"))

    @property
    def band_css(self):
        """The colour-named theme.css badge class for ``status_band`` — see :attr:`BAND_CSS`."""
        return self.BAND_CSS.get(self.status_band, "badge-muted")

    @property
    def dimension_display(self):
        """The dimension's frozen label, or ``Whole network`` for the roll-up row (``""``)."""
        return self.dimension_label or "Whole network"
