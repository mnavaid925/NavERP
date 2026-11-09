from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetMaintenanceSchedule(TenantNumbered):
    """
    Time-based, meter-based, and condition-based recurring preventive maintenance
    service calendars, inspection checklists, and lead-time reminders [AMSC-].
    """

    NUMBER_PREFIX = "AMSC"

    SCHEDULE_TYPE_CHOICES = [
        ("time_based", "Time-Based (Calendar Recurring)"),
        ("meter_based", "Meter / Runtime Hours Based"),
        ("condition_based", "Condition / Anomaly Triggered"),
        ("seasonal_shutdown", "Seasonal / Annual Turnaround"),
    ]

    FREQUENCY_UNIT_CHOICES = [
        ("days", "Days"),
        ("weeks", "Weeks"),
        ("months", "Months"),
        ("years", "Years"),
        ("runtime_hours", "Runtime Hours"),
        ("cycles_count", "Operating Cycles"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("overdue", "Overdue for Service"),
        ("paused", "Paused / Standby"),
        ("completed", "Completed"),
        ("retired", "Retired"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "overdue": "badge-red",
        "paused": "badge-amber",
        "completed": "badge-info",
        "retired": "badge-muted",
    }

    SCHEDULE_TYPE_CSS = {
        "time_based": "badge-info",
        "meter_based": "badge-purple",
        "condition_based": "badge-amber",
        "seasonal_shutdown": "badge-slate",
    }

    name = models.CharField(
        max_length=255,
        help_text="Preventive maintenance plan title (e.g. Monthly Hydraulic Filter Check)",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_schedules",
        help_text="Financial Fixed Asset covered",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_schedules",
        help_text="Operational machinery / equipment master",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_schedules",
        help_text="Category template applying to multiple assets of this type",
    )
    schedule_type = models.CharField(
        max_length=32,
        choices=SCHEDULE_TYPE_CHOICES,
        default="time_based",
        help_text="Recurrence trigger mechanism",
    )
    frequency_interval = models.PositiveIntegerField(
        default=30,
        help_text="Recurrence interval count (e.g. 30 for 30 days, 250 for 250 runtime hours)",
    )
    frequency_unit = models.CharField(
        max_length=20,
        choices=FREQUENCY_UNIT_CHOICES,
        default="days",
        help_text="Unit of recurrence frequency",
    )
    meter_trigger_threshold = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target meter delta threshold between PM services",
    )
    lead_time_days = models.PositiveIntegerField(
        default=7,
        help_text="Advance notice lead time in days before maintenance is due",
    )
    last_service_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this preventive service was last performed",
    )
    last_service_meter = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Meter reading recorded during last service",
    )
    next_due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Target calendar date when next service must be completed",
    )
    next_due_meter = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Meter reading threshold when next service is due",
    )
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_schedules",
        help_text="Default technician assigned to execute this PM checklist",
    )
    preferred_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_schedules",
        help_text="Preferred external service provider / contractor",
    )
    service_contract = models.ForeignKey(
        "assets.AssetServiceContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_schedules",
        help_text="Linked service agreement covering routine visits",
    )
    service_checklist = models.TextField(
        blank=True,
        help_text="Standard operating procedure and safety checklist (one task per line)",
    )
    is_mandatory = models.BooleanField(
        default=True,
        help_text="Statutory / safety compliance requirement",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this recurring maintenance schedule is active",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Current scheduling compliance state",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["next_due_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_amsc_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_amsc_ten_stat"),
            models.Index(fields=["tenant", "next_due_date"], name="idx_amsc_ten_due"),
            models.Index(fields=["tenant", "schedule_type"], name="idx_amsc_ten_type"),
            models.Index(fields=["tenant", "is_active"], name="idx_amsc_ten_act"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    @property
    def status_css(self):
        if self.is_active and self.next_due_date and self.next_due_date < timezone.now().date():
            return "badge-red"
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def schedule_type_css(self):
        return self.SCHEDULE_TYPE_CSS.get(self.schedule_type, "badge-slate")

    def checklist_items(self):
        if not self.service_checklist:
            return []
        return [line.strip() for line in self.service_checklist.splitlines() if line.strip()]

    def recalculate_next_due(self, from_date=None, from_meter=None):
        base_date = from_date or self.last_service_date or timezone.now().date()
        if self.frequency_unit == "days":
            self.next_due_date = base_date + timedelta(days=self.frequency_interval)
        elif self.frequency_unit == "weeks":
            self.next_due_date = base_date + timedelta(weeks=self.frequency_interval)
        elif self.frequency_unit == "months":
            # approximate 30 days per month
            self.next_due_date = base_date + timedelta(days=self.frequency_interval * 30)
        elif self.frequency_unit == "years":
            self.next_due_date = base_date + timedelta(days=self.frequency_interval * 365)

        if from_meter is not None and self.meter_trigger_threshold:
            self.next_due_meter = from_meter + self.meter_trigger_threshold
        elif self.last_service_meter is not None and self.meter_trigger_threshold:
            self.next_due_meter = self.last_service_meter + self.meter_trigger_threshold

    def record_completion(self, completion_date, completion_meter=None, user=None):
        self.last_service_date = completion_date
        if completion_meter is not None:
            self.last_service_meter = completion_meter
        self.recalculate_next_due(from_date=completion_date, from_meter=completion_meter)
        self.status = "active"
        self.save()

    def activate(self):
        self.is_active = True
        self.status = "active"
        self.save(update_fields=["is_active", "status", "updated_at"])

    def pause(self):
        self.is_active = False
        self.status = "paused"
        self.save(update_fields=["is_active", "status", "updated_at"])
