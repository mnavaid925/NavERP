"""SCM 4.7 Demand Planning — DemandForecast + DemandForecastPeriod.

The spine of the sub-module: a statistical forecast for one item (optionally at one location, for one
customer) across a bucketed horizon. The other three 4.7 models hang off it — signals adjust it,
adjustments build consensus on it, and the safety-stock calculator sizes buffers from its error.

**The decomposition IS the feature.** Each period keeps its numbers in SEPARATE columns:

    historical → baseline → × seasonal index → + event uplift → + signal adjustment
              → + consensus → final

so a planner can see *why* a number moved, not just that it did — the "glass box" every enterprise
demand-planning product sells. Overwriting one shared ``quantity`` column would throw that away.

**No stored history.** ``history_series()`` derives it from 4.5's ``SalesOrderLine`` / 4.3's
``StockMove`` on demand (``_history.py``); the accuracy metrics compare those live actuals against
what was forecast. Only the forecast itself is stored.
"""
from datetime import date, timedelta

from apps.scm.models._base import *  # noqa: F401,F403


def _months_before(value, months):
    """First day of the month ``months`` before ``value``'s month."""
    total = value.year * 12 + (value.month - 1) - int(months or 0)
    year, month = divmod(total, 12)
    return date(max(year, 1), month + 1, 1)


def _same_period_last_year(value, bucket):
    """The comparable period one year back, staying aligned to the bucket's grid."""
    if bucket == "week":
        return value - timedelta(days=364)  # 52 whole weeks — keeps the Monday alignment
    if bucket == "day":
        return value - timedelta(days=365)
    try:
        return date(value.year - 1, value.month, value.day)
    except ValueError:  # 29 Feb in a non-leap year
        return date(value.year - 1, value.month, 28)


class DemandForecast(TenantNumbered):
    """A statistical demand forecast [DF-] for one item over a bucketed horizon."""

    NUMBER_PREFIX = "DF"

    DEMAND_SOURCE_CHOICES = [
        ("sales_orders", "Sales Orders"),
        ("stock_issues", "Stock Issues"),
        ("manual", "Manual"),
    ]
    BUCKET_CHOICES = [
        ("day", "Day"),
        ("week", "Week"),
        ("month", "Month"),
        ("quarter", "Quarter"),
    ]
    METHOD_CHOICES = [
        ("naive", "Naive"),
        ("seasonal_naive", "Seasonal Naive"),
        ("moving_average", "Moving Average"),
        ("weighted_moving_average", "Weighted Moving Average"),
        ("exponential_smoothing", "Exponential Smoothing"),
        ("holt_linear", "Holt Linear Trend"),
        ("holt_winters", "Holt-Winters"),
        ("like_item", "Like-Item Copy"),
        ("manual", "Manual"),
        ("best_fit", "Best Fit"),
    ]
    SCENARIO_CHOICES = [
        ("baseline", "Baseline"),
        ("optimistic", "Optimistic"),
        ("pessimistic", "Pessimistic"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("statistical", "Statistical"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("archived", "Archived"),
    ]
    # An approved forecast is the plan of record and an archived one is history — neither may be
    # edited in place. Revise it instead (which clones it and supersedes the original).
    EDITABLE_STATUSES = ("draft", "statistical", "in_review")
    #: A horizon may not exceed this many buckets. The grid is ONE DB ROW PER BUCKET, so an
    #: unbounded span is an unbounded bulk_create: a 1900→9999 daily horizon is ~3 million rows in
    #: one statement, which any logged-in planner could trigger by pressing Generate. 520 is 10
    #: years of weeks / 43 years of months — far past any real plan.
    MAX_HORIZON_PERIODS = 520
    #: Guards `history_window()`'s date arithmetic, which raises OverflowError below year 1.
    MIN_HORIZON_YEAR = 1900
    #: Statuses whose periods a signal or adjustment may still move.
    ADJUSTABLE_STATUSES = ("statistical", "in_review", "approved")

    name = models.CharField(max_length=255)
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="demand_forecasts")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="demand_forecasts",
                                 help_text="Leave blank to forecast the whole network")
    customer = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="demand_forecasts",
                                 help_text="Leave blank to forecast all channels")
    demand_source = models.CharField(max_length=14, choices=DEMAND_SOURCE_CHOICES, default="sales_orders",
                                     help_text="Which live ledger the derived history reads from")
    bucket = models.CharField(max_length=8, choices=BUCKET_CHOICES, default="month")
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    history_months = models.PositiveIntegerField(
        default=24, validators=[MinValueValidator(1), MaxValueValidator(120)],
        help_text="How far back the derived history series reaches")
    method = models.CharField(max_length=24, choices=METHOD_CHOICES, default="moving_average")
    method_parameter = models.DecimalField(
        max_digits=8, decimal_places=4, default=3,
        help_text="Window N for the averages; alpha (0-1) for smoothing; season length for Holt-Winters")
    # What best_fit actually picked — stamped by generate, never typed.
    selected_method = models.CharField(max_length=32, blank=True, editable=False)
    seasonality_profile = models.ForeignKey("scm.SeasonalityProfile", on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name="forecasts")
    reference_item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="forecast_references",
                                       help_text="Like-item source for a product with no history")
    reference_scale_pct = models.DecimalField(max_digits=6, decimal_places=2, default=100,
                                              validators=[MinValueValidator(ZERO)],
                                              help_text="% of the reference item's demand to copy")
    exclude_outliers = models.BooleanField(default=False,
                                           help_text="Clamp spikes/dips in history before fitting")
    outlier_threshold_sigma = models.DecimalField(max_digits=4, decimal_places=2, default=3,
                                                  validators=[MinValueValidator(Decimal("0.5"))])
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_demand_forecasts",
                                 help_text="Display only — a forecast posts no journal entry")
    scenario = models.CharField(max_length=12, choices=SCENARIO_CHOICES, default="baseline")
    # Plan-of-record versioning, both stamped by the revise action.
    revision = models.PositiveIntegerField(default=1, editable=False)
    supersedes = models.ForeignKey("scm.DemandForecast", on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="superseded_by")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft", editable=False)
    generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="scm_forecasts_approved")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-horizon_start", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_df_tnt_status_idx"),
            models.Index(fields=["tenant", "item"], name="scm_df_tnt_item_idx"),
        ]

    def clean(self):
        errors = {}
        if self.horizon_start and self.horizon_end:
            if self.horizon_end < self.horizon_start:
                errors["horizon_end"] = "The horizon cannot end before it starts."
            elif self.horizon_start.year < self.MIN_HORIZON_YEAR:
                errors["horizon_start"] = (
                    f"The horizon must start in {self.MIN_HORIZON_YEAR} or later.")
            else:
                # The span is bounded HERE rather than in the view, so the form, the seeder and
                # `revise` all inherit the cap. period_COUNT, not len(period_range()): building the
                # range to measure it is the runaway allocation this check exists to stop.
                from apps.scm.models.DemandPlanning._history import period_count
                span = period_count(self.horizon_start, self.horizon_end, self.bucket)
                if span > self.MAX_HORIZON_PERIODS:
                    errors["horizon_end"] = (
                        f"That horizon is {span} {self.get_bucket_display().lower()} periods; the "
                        f"maximum is {self.MAX_HORIZON_PERIODS}. Use a coarser bucket or a shorter "
                        f"horizon.")
        if self.method == "like_item" and self.reference_item_id is None:
            errors["reference_item"] = "A like-item forecast needs a reference item to copy from."
        if self.reference_item_id and self.reference_item_id == self.item_id:
            errors["reference_item"] = "The reference item must be a different item."
        # `customer` narrows the derived history only on the sales_orders path — a StockMove has no
        # customer. Allowing the pair would fit and grade the forecast across ALL channels while its
        # header claimed one, which is worse than refusing it.
        if self.customer_id and self.demand_source == "stock_issues":
            errors["customer"] = ("Stock issues carry no customer — pick the Sales Orders source to "
                                  "forecast one channel, or clear the customer.")
        if errors:
            raise ValidationError(errors)

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def effective_method(self):
        """What actually produced the numbers — the chosen method, or best_fit's winner."""
        return self.selected_method or self.method

    @property
    def effective_method_display(self):
        """The human label for ``effective_method``.

        ``selected_method`` is a plain CharField, so Django generates no ``get_..._display`` for it
        and a template would otherwise print the raw ``weighted_moving_average`` slug next to a
        properly-labelled sibling column.
        """
        return dict(self.METHOD_CHOICES).get(self.effective_method, self.effective_method)

    # ---------------------------------------------------------------- derived history + generation
    def history_window(self):
        """``(start, end)`` of the history the fit reads — everything before the horizon opens."""
        end = self.horizon_start - timedelta(days=1)
        return _months_before(self.horizon_start, self.history_months or 24), end

    def history_series(self, item=None):
        """The derived demand series this forecast is fitted on — NEVER stored (see _history.py)."""
        from apps.scm.models.DemandPlanning._history import demand_series
        start, end = self.history_window()
        # tenant_ID, not tenant: demand_series only ever filters on it, and dereferencing the FK
        # costs a SELECT on core_tenant every time these run — once per row wherever they run in a loop.
        return demand_series(
            self.tenant_id, item=item or self.item, location=self.location, customer=self.customer,
            source=self.demand_source, start=start, end=end, bucket=self.bucket,
            exclude_outliers=self.exclude_outliers, sigma=self.outlier_threshold_sigma)

    def period_actuals_map(self):
        """``{period_start: actual_quantity}`` across the horizon in ONE pass.

        Batched deliberately: an accuracy panel that asked each period for its own actual would fire
        one aggregate per row, and the league-table report would multiply that by every forecast.
        """
        from apps.scm.models.DemandPlanning._history import demand_series
        rows = demand_series(self.tenant_id, item=self.item, location=self.location,
                             customer=self.customer, source=self.demand_source,
                             start=self.horizon_start, end=self.horizon_end, bucket=self.bucket)
        return {period_start: qty for period_start, qty in rows}

    @transaction.atomic
    def generate_periods(self, regenerate_locked=False):
        """(Re)build the period grid from the derived history. Returns how many rows were written.

        Locked periods are left completely untouched unless ``regenerate_locked`` — a planner locks a
        period precisely so a re-run cannot overwrite the number they committed to.
        """
        from apps.scm.models.DemandPlanning import _forecasting as fx
        from apps.scm.models.DemandPlanning._history import (period_label, period_range,
                                                             periods_per_year)  # noqa: F401

        # Capped at the walk, not after it — belt and braces behind clean(), since generate is also
        # reachable on rows written before the cap existed or outside a form, and this is the call
        # that turns a span into DB rows.
        buckets = period_range(self.horizon_start, self.horizon_end, self.bucket,
                               limit=self.MAX_HORIZON_PERIODS)
        if not buckets:
            return 0
        horizon = len(buckets)
        season = periods_per_year(self.bucket)

        # Like-item copies the REFERENCE item's history; everything else fits this item's own.
        use_reference = self.method == "like_item" and self.reference_item_id
        series = self.history_series(item=self.reference_item if use_reference else None)
        history_map = dict(series)
        values = [qty for _, qty in series]

        selected, projected = self.method, None
        if self.method == "best_fit":
            selected, projected = fx.best_fit(values, horizon, season_period=season)
        elif self.method == "like_item":
            scale = (self.reference_scale_pct or Decimal("100")) / Decimal("100")
            projected = [v * scale for v in fx.run_method("seasonal_naive", values, horizon,
                                                          season_period=season)]
        elif self.method != "manual":
            projected = fx.run_method(self.method, values, horizon, self.method_parameter, season)

        profile = self.seasonality_profile if (
            self.seasonality_profile_id and self.seasonality_profile.is_active) else None
        index_map = profile.index_map() if profile else None

        existing = {row.sequence: row for row in self.periods.all()}
        created, updated = [], []
        for index, (period_start, period_end) in enumerate(buckets, start=1):
            row = existing.get(index)
            if row is not None and row.is_locked and not regenerate_locked:
                continue
            if row is None:
                row = DemandForecastPeriod(forecast=self, sequence=index)
            row.period_start, row.period_end = period_start, period_end
            row.period_label = period_label(period_start, self.bucket)
            row.historical_quantity = _q4(
                history_map.get(_same_period_last_year(period_start, self.bucket), ZERO))
            if projected is not None:
                row.baseline_quantity = _q4(projected[index - 1])
                if profile is not None:
                    seasonal, uplift = profile.apply_to(row.baseline_quantity, period_start, index_map)
                    row.seasonal_index_applied, row.event_uplift_quantity = _q4(seasonal), _q4(uplift)
                else:
                    # A profile that was cleared or deactivated must RESET these columns. Leaving
                    # them would keep applying a curve the planner removed, silently, forever.
                    row.seasonal_index_applied, row.event_uplift_quantity = Decimal("1"), ZERO
                row.final_quantity = _q4(row.pre_adjustment_quantity + (row.consensus_quantity or ZERO))
            (updated if row.pk else created).append(row)

        DemandForecastPeriod.objects.bulk_create(created)
        if updated:
            # `manual` writes NO quantities — the planner typed them, and a regenerate that reset
            # them to zero would delete the only input the method has. It still refreshes the grid's
            # dates, labels and the history snapshot, which are derived either way.
            fields = ["period_start", "period_end", "period_label", "historical_quantity"]
            if projected is not None:
                fields += ["baseline_quantity", "seasonal_index_applied", "event_uplift_quantity",
                           "final_quantity"]
            DemandForecastPeriod.objects.bulk_update(updated, fields)
        # A shortened horizon leaves orphan rows behind; locked ones are the planner's, so they stay.
        self.periods.filter(sequence__gt=horizon, is_locked=False).delete()

        self.selected_method = selected if self.method == "best_fit" else ""
        self.generated_at = timezone.now()
        if self.status == "draft":
            self.status = "statistical"
        self.save(update_fields=["selected_method", "generated_at", "status", "updated_at"])
        self.recompute_consensus()
        return len(created) + len(updated)

    @transaction.atomic
    def recompute_consensus(self):
        """Roll ACCEPTED adjustments up into each period's ``consensus_quantity`` and refresh ``final``.

        Rebuilt from scratch over every accepted adjustment, oldest first, so a reject after an
        accept correctly backs its delta out again.

        Each adjustment is **re-resolved against the number as it stands when its turn comes**, not
        against the base that existed the day it was accepted. That matters for the non-``delta``
        types: two accepted "absolute 40" proposals on one period both mean *the period should be
        40*, so replaying a stale delta twice would land on 80; and after a regenerate moves the
        baseline, a stale absolute/percent delta would be measured against a number that no longer
        exists. ``resolved_quantity`` is written back so the screens show what was actually applied.

        An adjustment aimed at one period lands there; a horizon-wide one is disaggregated PRO-RATA
        across the periods (evenly when the pre-adjustment total is zero), which is the standard
        top-down split — spreading it evenly over a seasonal horizon would quietly flatten the curve.

        Locked periods are excluded entirely: a lock means "this number is committed", so it takes no
        share of a horizon-wide adjustment and its consensus column is left alone rather than showing
        a delta that its ``final_quantity`` does not include.
        """
        periods = [row for row in self.periods.all() if not row.is_locked]
        if not periods:
            return 0
        pre = {row.pk: row.pre_adjustment_quantity for row in periods}
        consensus = {row.pk: ZERO for row in periods}
        resolved = []
        for adjustment in self.adjustments.filter(status="accepted").order_by("created_at", "id"):
            if adjustment.period_id in consensus:
                base = pre[adjustment.period_id] + consensus[adjustment.period_id]
                delta = adjustment.delta_against(base)
                consensus[adjustment.period_id] += delta
            elif adjustment.period_id is not None:
                continue  # aimed at a locked (or foreign) period — it takes no effect here
            else:
                base = sum(pre.values(), ZERO) + sum(consensus.values(), ZERO)
                delta = adjustment.delta_against(base)
                weights = {row.pk: pre[row.pk] for row in periods}
                weight_total = sum(weights.values(), ZERO)
                for row in periods:
                    consensus[row.pk] += (delta * weights[row.pk] / weight_total
                                          if weight_total > ZERO else delta / Decimal(len(periods)))
            if adjustment.resolved_quantity != _q4(delta):
                adjustment.resolved_quantity = _q4(delta)
                resolved.append(adjustment)
        for row in periods:
            row.consensus_quantity = _q4(consensus[row.pk])
            row.final_quantity = _q4(pre[row.pk] + row.consensus_quantity)
        DemandForecastPeriod.objects.bulk_update(periods, ["consensus_quantity", "final_quantity"])
        if resolved:
            self.adjustments.model.objects.bulk_update(resolved, ["resolved_quantity"])
        return len(periods)

    # ---------------------------------------------------------------- accuracy (all derived)
    def accuracy_metrics(self, periods=None, actuals=None):
        """MAPE / WMAPE / bias / tracking signal / FVA over the ELAPSED part of the horizon.

        Only fully-elapsed periods are scored — grading a month that is still running would report a
        huge under-forecast every time. Returns ``{...: None}`` when nothing has elapsed yet.
        """
        from apps.scm.models.DemandPlanning import _forecasting as fx
        periods = list(self.periods.all()) if periods is None else periods
        actuals = self.period_actuals_map() if actuals is None else actuals
        today = timezone.localdate()
        scored = [row for row in periods if row.period_end and row.period_end < today]
        if not scored:
            return {"mape": None, "wmape": None, "bias_pct": None, "tracking_signal": None,
                    "fva": None, "points": 0}
        actual = [actuals.get(row.period_start, ZERO) for row in scored]
        final = [row.final_quantity or ZERO for row in scored]
        baseline = [row.baseline_quantity or ZERO for row in scored]
        return {
            "mape": fx.mape(actual, final),
            "wmape": fx.wmape(actual, final),
            "bias_pct": fx.bias_pct(actual, final),
            "tracking_signal": fx.tracking_signal(actual, final),
            "fva": fx.forecast_value_added(actual, baseline, final),
            "points": len(scored),
        }

    def total_forecast_quantity(self):
        return self.periods.aggregate(s=Sum("final_quantity"))["s"] or ZERO

    def __str__(self):
        return f"{self.number or 'DF'} · {self.item.sku if self.item_id else '?'}"


class DemandForecastPeriod(models.Model):
    """One bucket of a forecast's horizon, with the decomposition kept in separate columns.

    Tenant-less child, reached via ``forecast.tenant`` (the SalesOrderLine / LoadStop convention).
    """

    forecast = models.ForeignKey("scm.DemandForecast", on_delete=models.CASCADE, related_name="periods")
    sequence = models.PositiveIntegerField(default=1)
    period_start = models.DateField()
    period_end = models.DateField()
    period_label = models.CharField(max_length=32, blank=True)
    # The comparable actual one year back — the number the fit was reading, kept as a snapshot so the
    # waterfall still explains itself after the underlying orders change.
    historical_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    baseline_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            help_text="Statistical output before any adjustment — "
                                                      "and the INPUT on a manual forecast")
    # Outputs of the seasonality PROFILE, not planner inputs. They were briefly editable, which made
    # them unusable end to end: a regenerate correctly resets them (a cleared profile must not keep
    # applying its curve), so anything typed here was erased by the next Generate. The profile is
    # the input; these two are what it produced.
    seasonal_index_applied = models.DecimalField(max_digits=8, decimal_places=4, default=1,
                                                 editable=False)
    event_uplift_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                                editable=False)
    # Written by demandsignal_apply, not typed.
    signal_adjustment_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                                     editable=False)
    # Rolled up from ACCEPTED ForecastAdjustments by recompute_consensus(), not typed.
    consensus_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    # The bottom of the waterfall, recomputed by generate, by the grid save and by every
    # accept/reject. Never typed — see the class docstring.
    final_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                     validators=[MinValueValidator(ZERO)],
                                     help_text="Values the forecast in money alongside units")
    is_locked = models.BooleanField(default=False,
                                    help_text="A locked period survives a regenerate untouched")

    class Meta:
        ordering = ["forecast", "sequence"]
        unique_together = ("forecast", "sequence")

    @property
    def pre_adjustment_quantity(self):
        """Everything the model and the signals say, before human consensus — the waterfall up to
        (but not including) ``consensus_quantity``."""
        return ((self.baseline_quantity or ZERO) * (self.seasonal_index_applied or Decimal("1"))
                + (self.event_uplift_quantity or ZERO)
                + (self.signal_adjustment_quantity or ZERO))

    @property
    def seasonal_quantity(self):
        """Baseline after the seasonal index — the middle step of the waterfall."""
        return (self.baseline_quantity or ZERO) * (self.seasonal_index_applied or Decimal("1"))

    @property
    def forecast_value(self):
        return (self.final_quantity or ZERO) * (self.unit_price or ZERO)

    def __str__(self):
        return f"{self.period_label or self.period_start} · {self.final_quantity}"


#: The clamped quantizer every quantity write in this module goes through — defined once in
#: ``models/_base.py`` so the signal and adjustment writers cannot drift from it.
_q4 = q4
