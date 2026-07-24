"""SCM 4.7 Demand Planning — SeasonalityProfile + SeasonalityIndex.

**One table covers both halves of the NavERP "Seasonality Analysis" bullet** (seasonal peaks AND
promotional events). A recurring seasonal curve and a windowed promotion are the same object at
different ``profile_type``s: a set of per-period multipliers applied on top of a statistical baseline.
The only real difference is that a promotion/event has a finite ``event_start``/``event_end`` window
while a seasonal curve repeats forever. Splitting them into two tables would duplicate the index
child, the derive-from-history action and the whole CRUD surface to express that one difference.

``bucket="period_from_launch"`` is what lets the same index rows serve a product LIFECYCLE curve
(ramp-up / maturity / decay indexed off the launch date rather than off the calendar).

Index factors are **multipliers around 1.0000** — 1.2500 means "this period runs 25 % above the
de-seasonalised average". They can be typed by hand or filled by the derive action from the derived
demand series (there is no stored history table — see ``_history.py``).
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SeasonalityProfile(TenantNumbered):
    """A reusable curve of per-period demand multipliers [SEA-]."""

    NUMBER_PREFIX = "SEA"

    PROFILE_TYPE_CHOICES = [
        ("seasonal", "Seasonal"),
        ("promotion", "Promotion"),
        ("event", "Event"),
        ("lifecycle", "Lifecycle"),
    ]
    #: Types that describe a one-off window rather than a repeating calendar pattern.
    WINDOWED_TYPES = ("promotion", "event")
    BUCKET_CHOICES = [
        ("week", "Week"),
        ("month", "Month"),
        ("quarter", "Quarter"),
        ("period_from_launch", "Period From Launch"),
    ]
    SCOPE_CHOICES = [
        ("item", "Item"),
        ("category", "Category"),
        ("location", "Location"),
        ("global", "Global"),
    ]
    MECHANIC_CHOICES = [
        ("price_discount", "Price Discount"),
        ("bogo", "BOGO"),
        ("display", "Display"),
        ("advert", "Advertising"),
        ("bundle", "Bundle"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=255)
    profile_type = models.CharField(max_length=12, choices=PROFILE_TYPE_CHOICES, default="seasonal")
    bucket = models.CharField(max_length=20, choices=BUCKET_CHOICES, default="month",
                              help_text="Period grain the index rows are numbered in")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default="item")
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="seasonality_profiles")
    category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="seasonality_profiles")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="seasonality_profiles")
    event_start = models.DateField(null=True, blank=True,
                                   help_text="Required for a promotion/event — the window it applies in")
    event_end = models.DateField(null=True, blank=True)
    uplift_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                     help_text="Flat % uplift applied across the event window")
    cannibalization_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                              help_text="% of this uplift taken from the cannibalized category")
    cannibalized_category = models.ForeignKey("scm.ItemCategory", on_delete=models.SET_NULL, null=True,
                                              blank=True, related_name="cannibalized_by_profiles")
    promotion_mechanic = models.CharField(max_length=16, choices=MECHANIC_CHOICES, blank=True)
    derived_from_years = models.PositiveIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="How many prior years 'Derive from history' averages")
    # Stamped by the derive action, never typed.
    last_derived_at = models.DateTimeField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "profile_type"], name="scm_sea_tnt_type_idx")]

    def clean(self):
        errors = {}
        if self.profile_type in self.WINDOWED_TYPES:
            if not self.event_start or not self.event_end:
                errors["event_start"] = "A promotion or event needs both a start and an end date."
            elif self.event_end < self.event_start:
                errors["event_end"] = "The event cannot end before it starts."
        required_scope = {"item": "item", "category": "category", "location": "location"}.get(self.scope)
        if required_scope and getattr(self, f"{required_scope}_id", None) is None:
            errors[required_scope] = f"Scope '{self.get_scope_display()}' needs a {required_scope}."
        if errors:
            raise ValidationError(errors)

    def index_for_period(self, period_start):
        """Multiplier for a calendar date — 1.0000 when the profile does not cover it.

        A windowed promotion/event contributes ``1 + uplift_pct/100`` inside its window and nothing
        outside it; a seasonal/lifecycle profile looks its period number up in the index rows. Callers
        that apply this across a whole horizon should pass a prefetched ``indices`` list via
        ``index_map()`` instead of hitting this per period.
        """
        return self._index_from_map(period_start, self.index_map())

    def index_map(self):
        """``{period_number: index_factor}`` in ONE query — built once per generate/report pass."""
        return {row.period_number: row.index_factor for row in self.indices.all()}

    def apply_to(self, baseline, period_start, index_map=None):
        """Split this profile's effect on ``baseline`` into ``(seasonal_index, event_uplift)``.

        The two land in SEPARATE columns on the forecast period on purpose — the waterfall
        (baseline → × index → + uplift → …) is the explainability feature, so a recurring calendar
        pattern and a one-off promotion must never be collapsed into one adjusted number.
        """
        factor = self._index_from_map(period_start, index_map if index_map is not None else self.index_map())
        if self.profile_type in self.WINDOWED_TYPES:
            return Decimal("1"), (baseline or ZERO) * (factor - Decimal("1"))
        return factor, ZERO

    def _index_from_map(self, period_start, index_map):
        if self.profile_type in self.WINDOWED_TYPES:
            if self.event_start and self.event_end and not (
                    self.event_start <= period_start <= self.event_end):
                return Decimal("1")
            return Decimal("1") + (self.uplift_pct or ZERO) / Decimal("100")
        return index_map.get(self.period_number_for(period_start), Decimal("1"))

    def period_number_for(self, period_start):
        """Which index row a calendar date falls in, per this profile's bucket.

        ``period_from_launch`` is measured in MONTHS from ``event_start`` (the launch date) and is
        1-based, so a lifecycle curve's first row is period 1 — the launch month itself.
        """
        if self.bucket == "week":
            return period_start.isocalendar()[1]
        if self.bucket == "quarter":
            return (period_start.month - 1) // 3 + 1
        if self.bucket == "period_from_launch":
            if not self.event_start:
                return 1
            months = ((period_start.year - self.event_start.year) * 12
                      + period_start.month - self.event_start.month)
            return max(months + 1, 1)
        return period_start.month

    @property
    def expected_period_count(self):
        """How many index rows a complete curve has at this bucket (lifecycle curves are open-ended)."""
        return {"week": 53, "month": 12, "quarter": 4}.get(self.bucket)

    def __str__(self):
        return f"{self.number or 'SEA'} · {self.name}"


class SeasonalityIndex(models.Model):
    """One period's multiplier on a profile. Tenant-less child, reached via ``profile.tenant``
    (the SalesOrderLine / LoadStop / PurchaseOrderLine convention)."""

    profile = models.ForeignKey("scm.SeasonalityProfile", on_delete=models.CASCADE,
                                related_name="indices")
    period_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(366)],
        help_text="1-12 for months, 1-53 for weeks, 1-4 for quarters, months-from-launch for lifecycle")
    period_label = models.CharField(max_length=32, blank=True)
    index_factor = models.DecimalField(max_digits=8, decimal_places=4, default=1,
                                       validators=[MinValueValidator(ZERO)],
                                       help_text="1.0000 = neutral; 1.2500 = 25% above average")
    # How many history points the derive action averaged into this factor — a 1-sample index is a
    # guess, and the detail page says so rather than presenting it as a fitted curve.
    sample_size = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["profile", "period_number"]
        unique_together = ("profile", "period_number")

    @property
    def variance_pct(self):
        """How far above/below neutral this period runs, in percentage points."""
        return ((self.index_factor or Decimal("1")) - Decimal("1")) * Decimal("100")

    def __str__(self):
        return f"P{self.period_number} × {self.index_factor}"
