"""SCM 4.7 Demand Planning — DemandSignal (demand sensing).

A short-horizon observation log with a review → apply → measure triage, kept **deliberately separate
from ``DemandForecast``**: demand sensing runs on a different cadence (a rolling 4–8 week window),
has its own lifecycle, and is a different job for a different person, which is why the enterprise
suites ship it as a distinct engine rather than a field on the forecast.

Most signal types describe an EXTERNAL feed (retailer POS, channel inventory, weather, a customer's
own forecast). Those are hand-entered now and fed by an integration later — the same "store whatever
is posted, wire the feed when it exists" posture as 4.6's ``TrackingEvent``. What ships working today
is ``detect_order_surge()``: a real, internal detector that reads 4.5's live sales orders against the
approved forecast and raises signals with **zero integration required**.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403

#: Deviation from the approved forecast's run rate that raises a signal. Below this is noise.
SURGE_THRESHOLD_PCT = Decimal("20")


class DemandSignal(TenantNumbered):
    """A short-horizon demand observation [DS-] awaiting triage into a forecast."""

    NUMBER_PREFIX = "DS"

    SIGNAL_TYPE_CHOICES = [
        ("order_surge", "Order Surge"),
        ("order_dropoff", "Order Drop-Off"),
        ("pos_sell_through", "POS Sell-Through"),
        ("channel_inventory", "Channel Inventory"),
        ("customer_forecast", "Customer Forecast"),
        ("weather", "Weather"),
        ("competitor_action", "Competitor Action"),
        ("market_index", "Market Index"),
        ("social_sentiment", "Social Sentiment"),
        ("promotion_live", "Promotion Live"),
        ("supply_disruption", "Supply Disruption"),
        ("other", "Other"),
    ]
    SOURCE_CHOICES = [
        ("internal_orders", "Internal Orders"),
        ("internal_stock", "Internal Stock"),
        ("customer", "Customer"),
        ("retailer_pos", "Retailer POS"),
        ("market_data", "Market Data"),
        ("weather_service", "Weather Service"),
        ("manual", "Manual"),
        ("api", "API"),
    ]
    DIRECTION_CHOICES = [
        ("increase", "Increase"),
        ("decrease", "Decrease"),
        ("neutral", "Neutral"),
    ]
    CONFIDENCE_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("new", "New"),
        ("under_review", "Under Review"),
        ("applied", "Applied"),
        ("dismissed", "Dismissed"),
        ("expired", "Expired"),
    ]
    #: A signal may only be applied once, and only from the triage half of its lifecycle.
    APPLICABLE_STATUSES = ("new", "under_review")
    OPEN_STATUSES = ("new", "under_review")

    signal_type = models.CharField(max_length=20, choices=SIGNAL_TYPE_CHOICES, default="order_surge")
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="manual")
    source_reference = models.CharField(max_length=255, blank=True,
                                        help_text="Feed/document this came from — also the de-dupe key")
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="demand_signals")
    category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="demand_signals",
                                 help_text="Use instead of an item for a category-wide signal")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="demand_signals")
    customer = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="demand_signals")
    observed_at = models.DateTimeField()
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    horizon_days = models.PositiveIntegerField(
        default=28, validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Sensing window this signal is relevant for")
    signal_value = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                       help_text="What was observed (units, index, %, …)")
    baseline_value = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                         help_text="What was expected over the same window")
    impact_direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="increase")
    impact_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    impact_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                          help_text="Units to move the forecast by across the window")
    confidence = models.CharField(max_length=8, choices=CONFIDENCE_CHOICES, default="medium")
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="new", editable=False)
    applied_to_forecast = models.ForeignKey("scm.DemandForecast", on_delete=models.SET_NULL, null=True,
                                            blank=True, editable=False, related_name="applied_signals")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False,
                                    related_name="scm_demand_signals_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-observed_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_ds_tnt_status_idx"),
            models.Index(fields=["tenant", "signal_type"], name="scm_ds_tnt_type_idx"),
        ]

    def clean(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The window cannot end before it starts."})

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def signed_impact_quantity(self):
        """``impact_quantity`` carrying its direction — a drop-off pulls the forecast DOWN.

        The field is stored unsigned so a planner types a magnitude and picks a direction, rather
        than having to remember to type a minus sign.
        """
        magnitude = abs(self.impact_quantity or ZERO)
        if self.impact_direction == "decrease":
            return -magnitude
        if self.impact_direction == "neutral":
            return ZERO
        return magnitude

    def effective_window(self):
        """``(from, to)`` — falling back to ``observed_at`` + ``horizon_days`` when not stated."""
        start = self.effective_from or timezone.localtime(self.observed_at).date()
        end = self.effective_to or (start + timedelta(days=(self.horizon_days or 28) - 1))
        return start, end

    @transaction.atomic
    def apply_to_forecast(self, forecast, quantity=None):
        """Write this signal's impact into the forecast periods its window overlaps.

        The impact is a TOTAL across the window, disaggregated pro-rata by each overlapping period's
        seasonalised baseline (evenly when that total is zero) — the same top-down split
        ``recompute_consensus`` uses, so a seasonal horizon is not quietly flattened.

        Returns how many periods moved. Callers guard the status; this method does the arithmetic.
        """
        from apps.scm.models import DemandForecastPeriod
        start, end = self.effective_window()
        periods = [row for row in forecast.periods.all()
                   if row.period_end >= start and row.period_start <= end]
        if not periods:
            return 0
        total = Decimal(quantity if quantity is not None else self.signed_impact_quantity)
        weights = {row.pk: row.seasonal_quantity for row in periods}
        weight_total = sum(weights.values(), ZERO)
        for row in periods:
            share = (total * weights[row.pk] / weight_total) if weight_total > ZERO \
                else (total / Decimal(len(periods)))
            row.signal_adjustment_quantity = (
                (row.signal_adjustment_quantity or ZERO) + share).quantize(Decimal("0.0001"))
            if not row.is_locked:
                row.final_quantity = (row.pre_adjustment_quantity
                                      + (row.consensus_quantity or ZERO)).quantize(Decimal("0.0001"))
        DemandForecastPeriod.objects.bulk_update(
            periods, ["signal_adjustment_quantity", "final_quantity"])
        self.applied_to_forecast = forecast
        self.status = "applied"
        self.save(update_fields=["applied_to_forecast", "status", "updated_at"])
        return len(periods)

    def __str__(self):
        what = self.item.sku if self.item_id else (self.category.name if self.category_id else "network")
        return f"{self.number or 'DS'} · {self.get_signal_type_display()} · {what}"


# ------------------------------------------------------------------------------- sweeps
def expire_stale_signals(tenant):
    """Retire open signals whose effective window has already passed. Returns how many moved.

    A sensing signal is only actionable inside its window — after it closes, applying it to a
    forecast would move periods the observation never described. Without this, ``expired`` would be a
    status nothing ever set and the triage queue would accumulate dead rows forever.

    ``effective_to`` is nullable, so rows without one are resolved through ``effective_window()``
    (observation date + horizon) in Python rather than filtered in SQL — the open set is small by
    definition, since anything actioned has already left it.
    """
    if tenant is None:
        return 0
    today = timezone.localdate()
    stale = [signal for signal
             in DemandSignal.objects.filter(tenant=tenant, status__in=DemandSignal.OPEN_STATUSES)
             if signal.effective_window()[1] < today]
    for signal in stale:
        signal.status = "expired"
    if stale:
        DemandSignal.objects.bulk_update(stale, ["status"])
    return len(stale)


# ------------------------------------------------------------------------------- the live detector
def detect_order_surge(tenant, threshold_pct=SURGE_THRESHOLD_PCT):
    """Raise ``order_surge`` / ``order_dropoff`` signals from LIVE sales orders vs. approved forecasts.

    The one signal type that needs no external feed: for every approved forecast whose horizon covers
    today, the orders booked so far in the current period are extrapolated to a full-period run rate
    and compared against what was forecast. A deviation beyond ``threshold_pct`` becomes a signal for
    a planner to triage.

    Idempotent — ``source_reference`` carries ``<forecast number>:<period sequence>`` and an existing
    open/applied signal for that key is never duplicated, so the action (and the seeder) can be run
    repeatedly.
    """
    from apps.scm.models import DemandForecast
    from apps.scm.models.DemandPlanning._history import demand_series

    if tenant is None:
        return []
    today = timezone.localdate()
    forecasts = (DemandForecast.objects
                 .filter(tenant=tenant, status="approved",
                         horizon_start__lte=today, horizon_end__gte=today)
                 .select_related("item", "location", "customer"))
    created = []
    for forecast in forecasts:
        period = next((row for row in forecast.periods.all()
                       if row.period_start <= today <= row.period_end), None)
        if period is None or (period.final_quantity or ZERO) <= ZERO:
            continue
        reference = f"{forecast.number}:{period.sequence}"
        # Dismissed signals count too — a planner who has already decided this deviation is noise
        # should not be handed it again every time somebody presses the button.
        if DemandSignal.objects.filter(tenant=tenant, source_reference=reference).exists():
            continue
        elapsed = Decimal((today - period.period_start).days + 1)
        total_days = Decimal((period.period_end - period.period_start).days + 1)
        if elapsed <= ZERO or total_days <= ZERO:
            continue
        rows = demand_series(tenant, item=forecast.item, location=forecast.location,
                             customer=forecast.customer, source=forecast.demand_source,
                             start=period.period_start, end=today, bucket=forecast.bucket)
        actual = sum((qty for _, qty in rows), ZERO)
        run_rate = actual * total_days / elapsed
        expected = period.final_quantity
        deviation_pct = (run_rate - expected) * Decimal("100") / expected
        if abs(deviation_pct) < threshold_pct:
            continue
        created.append(DemandSignal.objects.create(
            tenant=tenant,
            signal_type="order_surge" if deviation_pct > ZERO else "order_dropoff",
            source="internal_orders", source_reference=reference,
            item=forecast.item, location=forecast.location, customer=forecast.customer,
            observed_at=timezone.now(),
            effective_from=today, effective_to=period.period_end,
            horizon_days=max((period.period_end - today).days + 1, 1),
            signal_value=run_rate.quantize(Decimal("0.0001")),
            baseline_value=expected,
            impact_direction="increase" if deviation_pct > ZERO else "decrease",
            # Clamped to what the DecimalField(6, 2) column holds. A tiny forecast against a real
            # order (2 planned, 250 ordered) yields a five-figure percentage, and an overflow here
            # would take the whole detection batch down with a DataError.
            impact_pct=min(abs(deviation_pct), Decimal("9999.99")).quantize(Decimal("0.01")),
            impact_quantity=abs(run_rate - expected).quantize(Decimal("0.0001")),
            confidence="high" if abs(deviation_pct) >= threshold_pct * 2 else "medium",
            notes=(f"Detected from live sales orders: {actual} ordered in "
                   f"{elapsed} of {total_days} days against a forecast of {expected}."),
        ))
    return created
