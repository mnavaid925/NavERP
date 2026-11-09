from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetPerformanceScorecard(TenantNumbered):
    """
    Asset performance scorecard, capacity utilization, reliability metrics (MTBF/MTTR),
    and multi-dimensional composite performance index benchmarking ledger [APSC-].
    """

    NUMBER_PREFIX = "APSC"

    PERIOD_TYPE_CHOICES = [
        ("daily", "Daily Rollup"),
        ("weekly", "Weekly Rollup"),
        ("monthly", "Monthly Scorecard"),
        ("quarterly", "Quarterly Scorecard"),
        ("annual", "Annual Scorecard"),
    ]

    BENCHMARK_GRADE_CHOICES = [
        ("grade_a", "Grade A - Benchmark Leader (90-100)"),
        ("grade_b", "Grade B - Reliable & Sound (75-89)"),
        ("grade_c", "Grade C - Needs Optimization (55-74)"),
        ("grade_d", "Grade D - Critical Performance Risk (<55)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Scorecard"),
        ("published", "Published / Certified"),
        ("archived", "Archived"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "published": "badge-green",
        "archived": "badge-muted",
    }

    PERIOD_CSS = {
        "daily": "badge-slate",
        "weekly": "badge-info",
        "monthly": "badge-info",
        "quarterly": "badge-amber",
        "annual": "badge-green",
    }

    GRADE_CSS = {
        "grade_a": "badge-green",
        "grade_b": "badge-info",
        "grade_c": "badge-amber",
        "grade_d": "badge-red",
    }

    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performance_scorecards",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performance_scorecards",
        help_text="Operational machinery record",
    )
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPE_CHOICES,
        default="monthly",
        help_text="Scorecard aggregation frequency",
    )
    period_start = models.DateField(
        help_text="Start date of evaluation window",
    )
    period_end = models.DateField(
        help_text="End date of evaluation window",
    )
    total_calendar_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("720.00"),
        help_text="Total calendar clock hours in evaluation window (e.g. 30 days × 24 hrs)",
    )
    planned_operating_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("480.00"),
        help_text="Budgeted available production hours",
    )
    actual_operating_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual running operating hours",
    )
    unplanned_downtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Hours lost to breakdown failures",
    )
    planned_downtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Hours allocated to scheduled PM and setups",
    )
    idle_capacity_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Available hours unutilized due to lack of demand/labor/materials",
    )
    capacity_utilization_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual Operating Hours / Planned Operating Hours * 100",
    )
    availability_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual Operating / (Actual Operating + Unplanned Downtime) * 100",
    )
    failure_event_count = models.IntegerField(
        default=0,
        help_text="Number of unexpected breakdown stoppage incidents in window",
    )
    mtbf_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Mean Time Between Failures: Operating Hours / Failure Count",
    )
    mttr_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Mean Time To Repair: Unplanned Downtime Hours / Failure Count",
    )
    average_oee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Average OEE composite percentage in period",
    )
    total_energy_consumption_kwh = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative energy consumption in kWh",
    )
    total_carbon_emissions_kg = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative Scope 1/2 GHG footprint in kg CO2e",
    )
    total_downtime_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative financial downtime loss in period",
    )
    performance_index_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weighted composite Asset Performance Index (0-100)",
    )
    benchmark_grade = models.CharField(
        max_length=15,
        choices=BENCHMARK_GRADE_CHOICES,
        default="grade_b",
        help_text="Letter grade benchmark classification",
    )
    peer_category_ranking = models.IntegerField(
        default=1,
        help_text="Rank within same asset category / department",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Scorecard publishing lifecycle",
    )
    executive_summary = models.TextField(
        blank=True,
        help_text="Reliability engineer commentary, recommendations, and bottlenecks",
    )
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_asset_scorecards",
        help_text="Reliability engineer or asset manager",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_performance_scorecards",
        help_text="Operating department or site cost center",
    )

    class Meta:
        ordering = ["-period_end", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_apsc_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_apsc_ten_stat"),
            models.Index(fields=["tenant", "-period_end"], name="idx_apsc_ten_pend"),
            models.Index(fields=["tenant", "period_type"], name="idx_apsc_ten_per"),
            models.Index(fields=["tenant", "benchmark_grade"], name="idx_apsc_ten_grd"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_apsc_ten_fa"),
        ]

    def __str__(self):
        asset_name = ""
        if self.fixed_asset:
            asset_name = f" - {self.fixed_asset.name}"
        elif self.operational_asset:
            asset_name = f" - {self.operational_asset.name}"
        return f"{self.number}{asset_name} ({self.get_period_type_display()}: Grade {self.get_benchmark_grade_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def period_css(self):
        return self.PERIOD_CSS.get(self.period_type, "badge-slate")

    @property
    def grade_css(self):
        return self.GRADE_CSS.get(self.benchmark_grade, "badge-slate")

    def calculate_scorecard(self):
        actual_hours = self.actual_operating_hours or Decimal("0.00")
        unplanned_hours = self.unplanned_downtime_hours or Decimal("0.00")
        planned_down = self.planned_downtime_hours or Decimal("0.00")
        planned_op = self.planned_operating_hours or Decimal("0.00")
        failures = self.failure_event_count or 0
        avg_oee = self.average_oee_percentage or Decimal("0.00")

        # 1. Idle capacity hours = planned - (actual + unplanned downtime + planned downtime)
        accounted = actual_hours + unplanned_hours + planned_down
        if planned_op > accounted:
            self.idle_capacity_hours = (planned_op - accounted).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            self.idle_capacity_hours = Decimal("0.00")

        # 2. Capacity Utilization Rate (%) = actual / planned * 100
        if planned_op > Decimal("0.00"):
            util = (actual_hours / planned_op) * Decimal("100.0")
            self.capacity_utilization_rate = min(Decimal("100.00"), max(Decimal("0.00"), util.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
        else:
            self.capacity_utilization_rate = Decimal("0.00")

        # 3. Availability Rate (%) = actual / (actual + unplanned) * 100
        active_and_down = actual_hours + unplanned_hours
        if active_and_down > Decimal("0.00"):
            avail = (actual_hours / active_and_down) * Decimal("100.0")
            self.availability_rate = min(Decimal("100.00"), max(Decimal("0.00"), avail.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
        else:
            self.availability_rate = Decimal("0.00")

        # 4. MTBF & MTTR
        if failures > 0:
            mtbf = actual_hours / Decimal(str(failures))
            self.mtbf_hours = mtbf.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            mttr = unplanned_hours / Decimal(str(failures))
            self.mttr_hours = mttr.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            self.mtbf_hours = actual_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            self.mttr_hours = Decimal("0.00")

        # 5. Composite Performance Index Score (0-100)
        # 35% Utilization + 35% Availability + 30% OEE
        score = (
            (self.capacity_utilization_rate * Decimal("0.35"))
            + (self.availability_rate * Decimal("0.35"))
            + (avg_oee * Decimal("0.30"))
        )
        self.performance_index_score = min(Decimal("100.00"), max(Decimal("0.00"), score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))

        # 6. Benchmark Grade
        if self.performance_index_score >= Decimal("90.00"):
            self.benchmark_grade = "grade_a"
        elif self.performance_index_score >= Decimal("75.00"):
            self.benchmark_grade = "grade_b"
        elif self.performance_index_score >= Decimal("55.00"):
            self.benchmark_grade = "grade_c"
        else:
            self.benchmark_grade = "grade_d"

    def save(self, *args, **kwargs):
        self.calculate_scorecard()
        super().save(*args, **kwargs)
