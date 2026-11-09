from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetDowntimeLog(TenantNumbered):
    """
    Asset outage and operational downtime event ledger [ADWN-].
    Tracks stoppage intervals, duration, failure modes, hourly financial loss,
    and MTBF/MTTR event attribution.
    """

    NUMBER_PREFIX = "ADWN"

    DOWNTIME_CATEGORY_CHOICES = [
        ("unplanned_breakdown", "Unplanned Breakdown"),
        ("planned_maintenance", "Planned Maintenance / PM"),
        ("setup_changeover", "Setup & Changeover"),
        ("tooling_adjustment", "Tooling & Adjustment"),
        ("process_interruption", "Process Interruption / Starvation"),
        ("utility_outage", "Utility / Power Failure"),
        ("operator_unavailable", "Operator / Staff Shortage"),
        ("cleaning_sanitation", "Cleaning & Sanitation"),
    ]

    IMPACT_LEVEL_CHOICES = [
        ("full_shutdown", "Full Machine Shutdown"),
        ("partial_derate", "Partial Derate / Speed Loss"),
        ("cell_idle", "Cell / Line Idle"),
        ("minor_stop", "Minor Stoppage (<5 min)"),
    ]

    STATUS_CHOICES = [
        ("active", "Active Stoppage"),
        ("resolved", "Resolved / Resumed"),
        ("under_investigation", "Under Root Cause Analysis"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "active": "badge-red",
        "resolved": "badge-green",
        "under_investigation": "badge-amber",
        "cancelled": "badge-muted",
    }

    CATEGORY_CSS = {
        "unplanned_breakdown": "badge-red",
        "planned_maintenance": "badge-info",
        "setup_changeover": "badge-info",
        "tooling_adjustment": "badge-slate",
        "process_interruption": "badge-amber",
        "utility_outage": "badge-red",
        "operator_unavailable": "badge-amber",
        "cleaning_sanitation": "badge-slate",
    }

    IMPACT_CSS = {
        "full_shutdown": "badge-red",
        "partial_derate": "badge-amber",
        "cell_idle": "badge-info",
        "minor_stop": "badge-slate",
    }

    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="downtime_logs",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="downtime_logs",
        help_text="Operational equipment record",
    )
    maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="downtime_logs",
        help_text="Associated breakdown ticket",
    )
    work_order = models.ForeignKey(
        "scm.MaintenanceWorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_downtime_logs",
        help_text="Linked maintenance work order",
    )
    downtime_category = models.CharField(
        max_length=30,
        choices=DOWNTIME_CATEGORY_CHOICES,
        default="unplanned_breakdown",
        help_text="Primary root classification of stoppage",
    )
    impact_level = models.CharField(
        max_length=20,
        choices=IMPACT_LEVEL_CHOICES,
        default="full_shutdown",
        help_text="Operational severity on machine throughput",
    )
    root_cause_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="ISO 14224 / FMEA failure code or description",
    )
    failure_description = models.TextField(
        help_text="Detailed symptom, alarm, or cause of stoppage",
    )
    started_at = models.DateTimeField(
        help_text="Exact timestamp when downtime started",
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Exact timestamp when machine resumed operation",
    )
    duration_minutes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated duration in minutes",
    )
    hourly_cost_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Standard production/labor loss cost per hour",
    )
    total_downtime_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated downtime financial loss",
    )
    is_mtbf_failure = models.BooleanField(
        default=True,
        help_text="Counted as random failure for MTBF reliability calculations",
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logged_asset_downtimes",
        help_text="Staff operator or technician who logged the stoppage",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_downtime_logs",
        help_text="Department or plant workshop",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Lifecycle state of the downtime incident",
    )
    resolution_notes = models.TextField(
        blank=True,
        help_text="Corrective action, repair notes, and restart procedure",
    )

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_adwn_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_adwn_ten_stat"),
            models.Index(fields=["tenant", "downtime_category"], name="idx_adwn_ten_cat"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_adwn_ten_fa"),
        ]

    def __str__(self):
        asset_name = ""
        if self.fixed_asset:
            asset_name = f" - {self.fixed_asset.name}"
        elif self.operational_asset:
            asset_name = f" - {self.operational_asset.name}"
        return f"{self.number}{asset_name} ({self.get_downtime_category_display()})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def category_css(self):
        return self.CATEGORY_CSS.get(self.downtime_category, "badge-slate")

    @property
    def impact_css(self):
        return self.IMPACT_CSS.get(self.impact_level, "badge-slate")

    def calculate_duration_and_cost(self):
        if self.started_at and self.ended_at and self.ended_at >= self.started_at:
            delta_seconds = Decimal(str((self.ended_at - self.started_at).total_seconds()))
            self.duration_minutes = (delta_seconds / Decimal("60.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif not self.ended_at and self.started_at:
            delta_seconds = Decimal(str(max(0.0, (timezone.now() - self.started_at).total_seconds())))
            self.duration_minutes = (delta_seconds / Decimal("60.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if self.hourly_cost_rate and self.duration_minutes:
            hours = self.duration_minutes / Decimal("60.0")
            self.total_downtime_cost = (hours * self.hourly_cost_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            self.total_downtime_cost = Decimal("0.00")

    def save(self, *args, **kwargs):
        self.calculate_duration_and_cost()
        super().save(*args, **kwargs)
