from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetOeeRecord(TenantNumbered):
    """
    Overall Equipment Effectiveness (OEE) and TPM Six Big Losses run/shift ledger [AOEE-].
    Computes Availability × Performance × Quality factors, tracks scrap/rework counts,
    and assigns World-Class benchmarking tiers.
    """

    NUMBER_PREFIX = "AOEE"

    BENCHMARK_TIER_CHOICES = [
        ("world_class", "World-Class (>=85%)"),
        ("acceptable", "Typical / Acceptable (60-84%)"),
        ("low", "Low / High Loss (<60%)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Entry"),
        ("finalized", "Finalized / Verified"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "finalized": "badge-green",
        "cancelled": "badge-muted",
    }

    TIER_CSS = {
        "world_class": "badge-green",
        "acceptable": "badge-info",
        "low": "badge-red",
    }

    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oee_records",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oee_records",
        help_text="Operational equipment record",
    )
    record_date = models.DateField(
        default=timezone.now,
        help_text="Production calendar date",
    )
    shift_name = models.CharField(
        max_length=50,
        default="Shift 1",
        help_text="Production shift (e.g. Day Shift, Shift A, 08:00-16:00)",
    )
    planned_production_time_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("480.00"),
        help_text="Scheduled operational duration in minutes (excluding planned breaks)",
    )
    operating_time_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual run time minutes during which asset was producing",
    )
    ideal_cycle_time_seconds = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("10.00"),
        help_text="Minimum theoretical design cycle time per unit in seconds",
    )
    total_units_produced = models.IntegerField(
        default=0,
        help_text="Total count of pieces or units manufactured",
    )
    good_units_produced = models.IntegerField(
        default=0,
        help_text="Count of first-pass defect-free units conforming to specs",
    )
    defect_units_count = models.IntegerField(
        default=0,
        help_text="Count of rejected scrap pieces",
    )
    rework_units_count = models.IntegerField(
        default=0,
        help_text="Count of units requiring rework before release",
    )

    # TPM Six Big Losses (in minutes)
    breakdown_loss_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Unplanned equipment failure loss minutes",
    )
    setup_loss_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Tooling changeover and adjustment loss minutes",
    )
    small_stops_loss_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Minor idling and brief stoppages (<5 min) minutes",
    )
    reduced_speed_loss_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Loss from running machine below rated nominal speed",
    )
    defect_loss_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Time lost manufacturing rejected scrap product",
    )
    startup_loss_minutes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Warm-up, ramp-up and initial production yield loss",
    )

    # Calculated OEE Metrics (0.00 to 100.00 %)
    availability_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Availability factor: Operating Time / Planned Production Time * 100",
    )
    performance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Performance factor: (Ideal Cycle Time * Total Units) / Operating Time * 100",
    )
    quality_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Quality factor: Good Units / Total Units * 100",
    )
    oee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Overall Equipment Effectiveness: A × P × Q / 10000",
    )
    benchmark_tier = models.CharField(
        max_length=20,
        choices=BENCHMARK_TIER_CHOICES,
        default="acceptable",
        help_text="Classified benchmarking tier based on OEE %",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Verification state of this shift entry",
    )
    notes = models.TextField(
        blank=True,
        help_text="Production log notes, operator comments, or bottlenecks",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_oee_entries",
        help_text="Operator, supervisor, or quality engineer who entered data",
    )

    class Meta:
        ordering = ["-record_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aoee_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "record_date"], name="idx_aoee_ten_date"),
            models.Index(fields=["tenant", "benchmark_tier"], name="idx_aoee_ten_tier"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_aoee_ten_fa"),
        ]

    def __str__(self):
        asset_name = ""
        if self.fixed_asset:
            asset_name = f" - {self.fixed_asset.name}"
        elif self.operational_asset:
            asset_name = f" - {self.operational_asset.name}"
        return f"{self.number}{asset_name} ({self.record_date} {self.shift_name} - OEE: {self.oee_percentage}%)"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def tier_css(self):
        return self.TIER_CSS.get(self.benchmark_tier, "badge-slate")

    def calculate_oee(self):
        planned_time = self.planned_production_time_minutes or Decimal("0.00")
        operating_time = self.operating_time_minutes or Decimal("0.00")
        ideal_cycle = self.ideal_cycle_time_seconds or Decimal("0.00")
        total_units = self.total_units_produced or 0
        good_units = self.good_units_produced or 0

        # 1. Availability factor = Operating Time / Planned Production Time * 100
        if planned_time > Decimal("0.00"):
            avail = (operating_time / planned_time) * Decimal("100.0")
            self.availability_percentage = min(Decimal("100.00"), max(Decimal("0.00"), avail.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
        else:
            self.availability_percentage = Decimal("0.00")

        # 2. Performance factor = (Ideal Cycle Time (sec) * Total Units) / (Operating Time (min) * 60) * 100
        operating_seconds = operating_time * Decimal("60.0")
        if operating_seconds > Decimal("0.00") and ideal_cycle > Decimal("0.00"):
            ideal_production_time = Decimal(str(total_units)) * ideal_cycle
            perf = (ideal_production_time / operating_seconds) * Decimal("100.0")
            self.performance_percentage = min(Decimal("100.00"), max(Decimal("0.00"), perf.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
        else:
            self.performance_percentage = Decimal("0.00")

        # 3. Quality factor = Good Units / Total Units * 100
        if total_units > 0:
            qual = (Decimal(str(good_units)) / Decimal(str(total_units))) * Decimal("100.0")
            self.quality_percentage = min(Decimal("100.00"), max(Decimal("0.00"), qual.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
        else:
            self.quality_percentage = Decimal("0.00")

        # 4. Overall OEE = A × P × Q / 10000
        oee = (self.availability_percentage * self.performance_percentage * self.quality_percentage) / Decimal("10000.0")
        self.oee_percentage = min(Decimal("100.00"), max(Decimal("0.00"), oee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))

        # 5. Benchmark Tier classification
        if self.oee_percentage >= Decimal("85.00"):
            self.benchmark_tier = "world_class"
        elif self.oee_percentage >= Decimal("60.00"):
            self.benchmark_tier = "acceptable"
        else:
            self.benchmark_tier = "low"

    def save(self, *args, **kwargs):
        self.calculate_oee()
        super().save(*args, **kwargs)
