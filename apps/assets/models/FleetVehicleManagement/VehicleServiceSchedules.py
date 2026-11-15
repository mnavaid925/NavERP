"""Vehicle Service Scheduling and Preventive Maintenance model (11.19)."""

from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class VehicleServiceSchedule(TenantNumbered):
    """Vehicle preventive maintenance intervals, DOT inspections, and service work orders [VSRV]."""

    NUMBER_PREFIX = "VSRV"

    SERVICE_TYPE_CHOICES = [
        ("engine_oil_filter", "Engine Oil & Filter Change"),
        ("tire_rotation_balance", "Tire Rotation & Balance"),
        ("brake_pad_rotor_service", "Brake Pad & Rotor Service"),
        ("transmission_fluid_service", "Transmission Fluid Service"),
        ("coolant_flush", "Cooling System / Antifreeze Flush"),
        ("air_cabin_filter", "Engine & Cabin Air Filter Replacement"),
        ("annual_dot_inspection", "Annual DOT / Commercial Safety Inspection"),
        ("emissions_test", "State Emissions Test / Smog Check"),
        ("spark_plug_replacement", "Spark Plug & Ignition Service"),
        ("battery_electrical_check", "12V / High-Voltage Battery Diagnostic"),
        ("wheel_alignment", "Four-Wheel Alignment"),
        ("general_preventive_pm", "General Preventive Maintenance (PM A/B/C)"),
    ]

    PRIORITY_CHOICES = [
        ("emergency_safety", "Emergency Safety Concern"),
        ("high_priority", "High Priority"),
        ("normal_routine", "Normal / Routine"),
        ("scheduled_pm", "Scheduled Preventive"),
    ]

    STATUS_CHOICES = [
        ("active_tracking", "Active Tracking"),
        ("due_soon", "Service Due Soon"),
        ("overdue", "Service Overdue"),
        ("in_service", "In Service / At Shop"),
        ("paused", "Paused / On Hold"),
        ("completed", "Completed & Logged"),
    ]

    STATUS_CSS = {
        "active_tracking": "badge-info",
        "due_soon": "badge-amber",
        "overdue": "badge-red",
        "in_service": "badge-amber",
        "paused": "badge-slate",
        "completed": "badge-green",
    }

    PRIORITY_CSS = {
        "emergency_safety": "badge-red",
        "high_priority": "badge-amber",
        "normal_routine": "badge-info",
        "scheduled_pm": "badge-slate",
    }

    vehicle = models.ForeignKey(
        "assets.FleetVehicle",
        on_delete=models.CASCADE,
        related_name="service_schedules",
        help_text="Fleet vehicle serviced",
    )
    service_title = models.CharField(max_length=150, help_text="e.g. 15,000 Mile Service PM-B")
    service_type = models.CharField(max_length=32, choices=SERVICE_TYPE_CHOICES, default="engine_oil_filter")
    service_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_service_contracts",
        help_text="Outsourced service facility, mechanic shop, or dealer",
    )
    warranty = models.ForeignKey(
        "assets.AssetWarranty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_services",
        help_text="Associated manufacturer warranty coverage",
    )
    maintenance_schedule = models.ForeignKey(
        "assets.AssetMaintenanceSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_service_schedules",
        help_text="Optional link to core asset maintenance schedule",
    )
    interval_mileage = models.PositiveIntegerField(
        default=5000,
        help_text="Recurring mileage trigger (e.g. every 5,000 miles)",
    )
    interval_months = models.PositiveSmallIntegerField(
        default=6,
        help_text="Recurring calendar interval (e.g. every 6 months)",
    )
    last_service_date = models.DateField(null=True, blank=True)
    last_service_odometer = models.PositiveIntegerField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    next_due_odometer = models.PositiveIntegerField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="scheduled_pm")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="active_tracking")
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_service_schedules",
        help_text="Global currency for maintenance costing",
    )
    is_warranty_covered = models.BooleanField(default=False)
    work_order_invoice_ref = models.CharField(max_length=80, blank=True, help_text="Shop work order or invoice number")
    technician_resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["next_due_date", "-number"]
        verbose_name = "Vehicle Service Schedule"
        verbose_name_plural = "Vehicle Service Schedules"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_vsrv_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "vehicle", "status"], name="idx_vsrv_ten_veh_stat"),
            models.Index(fields=["tenant", "status"], name="idx_vsrv_ten_stat"),
            models.Index(fields=["tenant", "next_due_date"], name="idx_vsrv_ten_ndate"),
            models.Index(fields=["tenant", "next_due_odometer"], name="idx_vsrv_ten_nodom"),
        ]

    def __str__(self):
        return f"{self.number} — {self.service_title} ({self.vehicle.name})"

    def refresh_status(self, today=None):
        if today is None:
            today = timezone.now().date()
        if self.status in ("in_service", "paused", "completed"):
            return

        is_odometer_overdue = (
            self.next_due_odometer is not None
            and self.vehicle is not None
            and self.vehicle.current_odometer >= self.next_due_odometer
        )
        is_date_overdue = self.next_due_date is not None and self.next_due_date < today

        if is_odometer_overdue or is_date_overdue:
            self.status = "overdue"
            return

        is_odometer_soon = (
            self.next_due_odometer is not None
            and self.vehicle is not None
            and 0 <= (self.next_due_odometer - self.vehicle.current_odometer) <= 500
        )
        is_date_soon = (
            self.next_due_date is not None
            and today <= self.next_due_date <= today + timedelta(days=14)
        )
        if is_odometer_soon or is_date_soon:
            self.status = "due_soon"
        else:
            self.status = "active_tracking"

    def complete_service(self, completion_date, odometer, cost=Decimal("0.00"), notes=""):
        self.last_service_date = completion_date
        self.last_service_odometer = odometer
        if cost:
            self.actual_cost = cost
        if notes:
            self.technician_resolution_notes = notes

        # Roll forward next due targets
        if self.interval_months and completion_date:
            self.next_due_date = completion_date + timedelta(days=self.interval_months * 30)
        if self.interval_mileage and odometer:
            self.next_due_odometer = odometer + self.interval_mileage

        self.status = "active_tracking"
        self.save()

    @property
    def is_overdue(self):
        today = timezone.now().date()
        if self.next_due_date and self.next_due_date < today:
            return True
        if self.next_due_odometer and self.vehicle and self.vehicle.current_odometer >= self.next_due_odometer:
            return True
        return False

    @property
    def is_due_soon(self):
        if self.is_overdue:
            return False
        today = timezone.now().date()
        if self.next_due_date and today <= self.next_due_date <= today + timedelta(days=14):
            return True
        if self.next_due_odometer and self.vehicle and 0 <= (self.next_due_odometer - self.vehicle.current_odometer) <= 500:
            return True
        return False

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def priority_badge_class(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-slate")
