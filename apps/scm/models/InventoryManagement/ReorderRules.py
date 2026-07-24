"""SCM 4.3 Inventory Management — ReorderRule (safety-stock policy extended by 4.7).

A per-item, per-location reorder point + safety stock. The Reorder Alerts report lists rules whose
current on-hand has fallen to or below the reorder point and offers a one-click hand-off into 4.1's
`requisition_create` — the buyer still reviews and submits the requisition (no silent auto-PO). The
form is NOT pre-filled today; wiring the suggested quantity through is a documented follow-up.

**4.7 Demand Planning owns the CALCULATION of these numbers** (NavERP 4.7's "Safety Stock
Calculation" bullet) and extends this rule in place rather than declaring a second policy table — a
`SafetyStockPolicy` would duplicate this model's `(tenant, item, location)` grain and its
`safety_stock` column, and 4.4 already set the precedent by extending 4.3's `Location` with bin
attributes.

The extension is strictly ADDITIVE and the calculation writes ONLY to the `computed_*` columns:
`calculate()` proposes, and a separate reviewed **apply** action copies the proposal into the live
`safety_stock`/`reorder_point`. That contract is what keeps 4.3's existing alerts honest — those two
columns are what `reorder_alerts` and `suggested_quantity()` read, so silently recomputing them under
a buyer would change purchasing behaviour with nobody having agreed to it. `safety_stock_method`
defaults to `fixed`, which reproduces the pre-4.7 behaviour exactly.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403


class ReorderRule(TenantOwned):
    """Reorder point + safety stock for one item at one location."""

    SAFETY_STOCK_METHOD_CHOICES = [
        ("fixed", "Fixed"),
        ("service_level", "Service Level"),
        ("periodic_review", "Periodic Review"),
        ("avg_max", "Average-Max"),
        ("forecast_error", "Forecast Error"),
    ]
    ABC_CHOICES = [("A", "A"), ("B", "B"), ("C", "C")]
    XYZ_CHOICES = [("X", "X"), ("Y", "Y"), ("Z", "Z")]
    #: How many periods of derived history the calculator fits demand variability on.
    CALC_HISTORY_MONTHS = 12

    item = models.ForeignKey("scm.Item", on_delete=models.CASCADE, related_name="reorder_rules")
    location = models.ForeignKey("scm.Location", on_delete=models.CASCADE, related_name="reorder_rules")
    reorder_point = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        validators=[MinValueValidator(ZERO)],
                                        help_text="Reorder when on-hand falls to/below this")
    safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                       validators=[MinValueValidator(ZERO)])
    reorder_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                           validators=[MinValueValidator(ZERO)],
                                           help_text="Suggested quantity to reorder")
    is_active = models.BooleanField(default=True)

    # --- 4.7 safety-stock policy (inputs the planner sets) -----------------------------------------
    safety_stock_method = models.CharField(max_length=16, choices=SAFETY_STOCK_METHOD_CHOICES,
                                           default="fixed",
                                           help_text="'Fixed' keeps the hand-entered safety stock")
    service_level_pct = models.DecimalField(max_digits=5, decimal_places=2, default=95,
                                            validators=[MinValueValidator(ZERO),
                                                        MaxValueValidator(Decimal("100"))],
                                            help_text="Target cycle service level — sets the Z factor")
    lead_time_days = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(3650)],
                                                 help_text="Replenishment lead time in days")
    lead_time_variability_days = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                                     validators=[MinValueValidator(ZERO)],
                                                     help_text="Standard deviation of the lead time")
    review_period_days = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(3650)],
                                                     help_text="Review cycle T for periodic review")
    seasonality_profile = models.ForeignKey("scm.SeasonalityProfile", on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name="reorder_rules",
                                            help_text="Sizes the buffer for the upcoming season")
    demand_forecast = models.ForeignKey("scm.DemandForecast", on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="reorder_rules",
                                        help_text="Source of forecast-error sizing")

    # --- 4.7 calculated outputs (never typed, never auto-applied) ----------------------------------
    avg_daily_demand = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    demand_std_dev = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    abc_class = models.CharField(max_length=1, choices=ABC_CHOICES, blank=True, editable=False,
                                 help_text="Revenue rank — NOT Location.abc_class (bin velocity)")
    xyz_class = models.CharField(max_length=1, choices=XYZ_CHOICES, blank=True, editable=False,
                                 help_text="Demand-variability class from the coefficient of variation")
    computed_safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                                editable=False)
    computed_reorder_point = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                                 editable=False)
    last_calculated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["item__sku"]
        unique_together = ("tenant", "item", "location")
        indexes = [models.Index(fields=["tenant", "is_active"], name="scm_reorder_tnt_active_idx")]

    @staticmethod
    def on_hand_map(tenant, rules):
        """``{(item_id, location_id): qty}`` for every rule in ONE grouped query.

        Each of current_on_hand/is_below_point/suggested_quantity otherwise costs its own aggregate,
        so a page that walks the rules pays 2-3 queries PER RULE (perf review). Views build this map
        once and hand the figure to the methods below.
        """
        from apps.scm.models import StockMove
        pairs = [(r.item_id, r.location_id) for r in rules]
        if not pairs:
            return {}
        rows = (StockMove.objects
                .filter(tenant=tenant,
                        item_id__in={i for i, _ in pairs},
                        location_id__in={l for _, l in pairs})
                .values("item_id", "location_id")
                .annotate(q=Sum("quantity")))
        return {(r["item_id"], r["location_id"]): (r["q"] or ZERO) for r in rows}

    def current_on_hand(self, on_hand=None):
        """Live on-hand for this rule's item at its location. Pass ``on_hand`` (from on_hand_map)
        to reuse an already-resolved figure instead of paying for another aggregate."""
        if on_hand is not None:
            return on_hand
        return self.item.on_hand(location=self.location)

    def is_below_point(self, on_hand=None):
        return self.current_on_hand(on_hand) <= self.reorder_point

    def suggested_quantity(self, on_hand=None):
        """How much to bring back up to the reorder point + safety stock (never negative)."""
        target = (self.reorder_point or ZERO) + (self.safety_stock or ZERO)
        gap = target - self.current_on_hand(on_hand)
        if self.reorder_quantity and self.reorder_quantity > ZERO:
            return max(self.reorder_quantity, gap) if gap > ZERO else ZERO
        return gap if gap > ZERO else ZERO

    # ------------------------------------------------------------------ 4.7 safety-stock calculation
    def demand_history(self, series=None):
        """The derived daily-demand series this rule is sized from — NEVER a stored history table.

        ``series`` may be passed in by a batch caller (the safety-stock report calculates every rule
        in one pass) so a page does not re-derive the same item's history per rule.
        """
        if series is not None:
            return series
        # Imported inside the method: models/__init__ loads InventoryManagement BEFORE DemandPlanning,
        # so a module-level import would be a cycle (the on_hand_map precedent above).
        from apps.scm.models.DemandPlanning._history import demand_series
        end = timezone.localdate()
        start = end - timedelta(days=30 * self.CALC_HISTORY_MONTHS)
        return demand_series(self.tenant, item=self.item, location=self.location,
                             source="sales_orders", start=start, end=end, bucket="month")

    def calculate(self, series=None):
        """Compute the safety stock and reorder point this rule's policy implies.

        Writes ONLY the ``computed_*``/statistics columns — never ``safety_stock``/``reorder_point``,
        which stay under the buyer's control until ``apply_computed()`` is called. Returns
        ``(computed_safety_stock, computed_reorder_point)``.

        Methods:
          * ``fixed`` — keep the hand-entered safety stock; only the reorder point is re-derived.
          * ``service_level`` — the classic Z × √(L·σ_d² + d̄²·σ_L²), so lead-time variability counts
            as much as demand variability (ignoring σ_L is the usual way a "correct" formula still
            stocks out).
          * ``periodic_review`` — the same, over the review cycle plus the lead time (T + L).
          * ``avg_max`` — (max demand × max lead time) − (avg demand × avg lead time); no statistics,
            which is why buyers trust it when the history is thin.
          * ``forecast_error`` — sized from the linked forecast's WMAPE instead of raw history
            variability: the buffer covers how wrong the plan has actually been.
        """
        from apps.scm.models.DemandPlanning import _forecasting as fx

        series = self.demand_history(series)
        monthly = [qty for _, qty in series]
        per_day = Decimal("30.4375")  # mean days per month — buckets are monthly, policy is in days
        daily = [qty / per_day for qty in monthly]
        avg_daily = fx.mean(daily)
        sigma_daily = fx.std_dev(daily)
        lead = Decimal(self.lead_time_days or 0)
        sigma_lead = self.lead_time_variability_days or ZERO

        if self.safety_stock_method == "service_level":
            safety = self._service_level_safety(avg_daily, sigma_daily, lead, sigma_lead, lead)
        elif self.safety_stock_method == "periodic_review":
            window = lead + Decimal(self.review_period_days or 0)
            safety = self._service_level_safety(avg_daily, sigma_daily, lead, sigma_lead, window)
        elif self.safety_stock_method == "avg_max":
            max_daily = max(daily) if daily else ZERO
            max_lead = lead + sigma_lead
            safety = max(max_daily * max_lead - avg_daily * lead, ZERO)
        elif self.safety_stock_method == "forecast_error":
            safety = self._forecast_error_safety(avg_daily, sigma_daily, lead, sigma_lead)
        else:  # fixed — the buyer's number stands, exactly as it did before 4.7
            safety = self.safety_stock or ZERO

        safety = self._seasonal_scale(safety)
        self.avg_daily_demand = _q4(avg_daily)
        self.demand_std_dev = _q4(sigma_daily)
        self.xyz_class = self._xyz_class(avg_daily, sigma_daily)
        self.computed_safety_stock = _q2(max(safety, ZERO))
        self.computed_reorder_point = _q2(max(avg_daily * lead + safety, ZERO))
        self.last_calculated_at = timezone.now()
        return self.computed_safety_stock, self.computed_reorder_point

    def _service_level_safety(self, avg_daily, sigma_daily, lead, sigma_lead, window):
        """Z × √(window·σ_d² + d̄²·σ_L²) — demand variability AND lead-time variability."""
        from apps.scm.models.DemandPlanning import _forecasting as fx
        z = fx.z_for_service_level(self.service_level_pct)
        variance = window * (sigma_daily ** 2) + (avg_daily ** 2) * (sigma_lead ** 2)
        if variance <= ZERO:
            return ZERO
        return z * variance.sqrt()

    def _forecast_error_safety(self, avg_daily, sigma_daily, lead, sigma_lead):
        """Size the buffer from the linked forecast's measured error, falling back to σ of history.

        A plan that has been running 30 % wrong needs a buffer built on 30 %, not on how noisy the
        raw history looked — that is the whole point of tying safety stock to the forecast.
        """
        from apps.scm.models.DemandPlanning import _forecasting as fx
        if self.demand_forecast_id:
            error_pct = self.demand_forecast.accuracy_metrics().get("wmape")
            if error_pct is not None:
                z = fx.z_for_service_level(self.service_level_pct)
                lead_window = lead if lead > ZERO else Decimal("1")
                return z * avg_daily * (error_pct / Decimal("100")) * lead_window.sqrt()
        return self._service_level_safety(avg_daily, sigma_daily, lead, sigma_lead, lead)

    def _seasonal_scale(self, safety):
        """Lift/lower the buffer by the seasonal index of the period the lead time lands in.

        Sizing December's buffer on the annual average is exactly how a seasonal item stocks out in
        its peak, so the profile the planner already maintains is reused rather than duplicated.
        """
        if not self.seasonality_profile_id or not self.seasonality_profile.is_active:
            return safety
        target = timezone.localdate() + timedelta(days=self.lead_time_days or 0)
        return safety * self.seasonality_profile.index_for_period(target)

    @staticmethod
    def _xyz_class(avg_daily, sigma_daily):
        """X = steady (CV ≤ 0.5), Y = variable (≤ 1.0), Z = erratic. Blank when there is no demand."""
        if avg_daily <= ZERO:
            return ""
        cv = sigma_daily / avg_daily
        if cv <= Decimal("0.5"):
            return "X"
        return "Y" if cv <= Decimal("1") else "Z"

    @staticmethod
    def assign_abc_classes(tenant, rules):
        """Rank ``rules`` A/B/C by the revenue their item earned, in ONE grouped query.

        Pareto split on cumulative revenue: A covers the first 80 %, B the next 15 %, C the tail.
        Batch by nature — a rule's class only means something relative to its siblings — so this is a
        static method the report calls once, not a per-row property.

        NOTE: this is a REVENUE rank. ``Location.abc_class`` is 4.4's bin-VELOCITY attribute — a
        different axis on a different table. Do not conflate them.
        """
        from apps.scm.models import SalesOrderLine
        rules = list(rules)
        if not rules:
            return {}
        rows = (SalesOrderLine.objects
                .filter(sales_order__tenant=tenant, item_id__in={r.item_id for r in rules})
                .exclude(sales_order__status__in=("draft", "cancelled"))
                .values("item_id")
                .annotate(revenue=Sum(F("quantity_ordered") * F("unit_price"),
                                      output_field=models.DecimalField(max_digits=20,
                                                                       decimal_places=4))))
        revenue = {row["item_id"]: (row["revenue"] or ZERO) for row in rows}
        total = sum(revenue.values(), ZERO)
        ranked = sorted(rules, key=lambda r: revenue.get(r.item_id, ZERO), reverse=True)
        classes, cumulative = {}, ZERO
        for rule in ranked:
            if total <= ZERO:
                rule.abc_class = ""
            else:
                cumulative += revenue.get(rule.item_id, ZERO)
                share = cumulative * Decimal("100") / total
                rule.abc_class = "A" if share <= Decimal("80") else ("B" if share <= Decimal("95") else "C")
            classes[rule.pk] = rule.abc_class
        return classes

    def apply_computed(self):
        """Promote the calculated numbers into the LIVE columns 4.3's alerts read.

        Deliberately a separate, explicitly-invoked step: ``calculate()`` recommends, a person
        accepts. Returns the ``{field: [before, after]}`` diff for the audit log.
        """
        before = {"safety_stock": self.safety_stock, "reorder_point": self.reorder_point}
        self.safety_stock = self.computed_safety_stock or ZERO
        self.reorder_point = self.computed_reorder_point or ZERO
        self.save(update_fields=["safety_stock", "reorder_point", "updated_at"])
        return {"safety_stock": [str(before["safety_stock"]), str(self.safety_stock)],
                "reorder_point": [str(before["reorder_point"]), str(self.reorder_point)]}

    @property
    def safety_stock_variance(self):
        """Computed minus live — what applying the recommendation would change."""
        return (self.computed_safety_stock or ZERO) - (self.safety_stock or ZERO)

    @property
    def safety_stock_variance_pct(self):
        """Variance as a % of the live number. ``None`` when there is nothing to compare against."""
        live = self.safety_stock or ZERO
        if live <= ZERO:
            return None
        return self.safety_stock_variance * Decimal("100") / live

    def __str__(self):
        return f"Reorder {self.item_id and self.item.sku} @ {self.location_id and self.location.code}"


def _q2(value):
    return Decimal(value or ZERO).quantize(Decimal("0.01"))


def _q4(value):
    return Decimal(value or ZERO).quantize(Decimal("0.0001"))
