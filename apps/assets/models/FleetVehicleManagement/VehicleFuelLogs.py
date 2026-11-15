"""Vehicle Fuel Log & Consumption Tracking model (11.19)."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class VehicleFuelLog(TenantNumbered):
    """Vehicle fuel fill-up transaction, MPG efficiency, and fuel card log [VFUL]."""

    NUMBER_PREFIX = "VFUL"

    FUEL_TYPE_CHOICES = [
        ("regular_gasoline", "Regular Gasoline (87 Octane)"),
        ("premium_gasoline", "Premium Gasoline (91+ Octane)"),
        ("diesel_ultra_low_sulfur", "Ultra-Low Sulfur Diesel (ULSD)"),
        ("biodiesel", "Biodiesel Blend (B20)"),
        ("ev_kwh_charging", "EV kWh Fast Charging"),
        ("def_exhaust_fluid", "Diesel Exhaust Fluid (DEF)"),
        ("cng", "Compressed Natural Gas (CNG)"),
    ]

    ROUTE_CATEGORY_CHOICES = [
        ("city_local", "Urban / City Local"),
        ("highway_longhaul", "Highway / Long Haul"),
        ("mixed_delivery", "Mixed Route / Delivery"),
        ("job_site_idle", "Job Site / Heavy Idle"),
    ]

    EFFICIENCY_RATING_CHOICES = [
        ("optimal", "Optimal / High Efficiency"),
        ("acceptable", "Acceptable / Normal"),
        ("excessive_consumption", "Excessive Consumption"),
        ("anomalous", "Anomalous / Investigation Needed"),
    ]

    EFFICIENCY_CSS = {
        "optimal": "badge-green",
        "acceptable": "badge-info",
        "excessive_consumption": "badge-amber",
        "anomalous": "badge-red",
    }

    vehicle = models.ForeignKey(
        "assets.FleetVehicle",
        on_delete=models.CASCADE,
        related_name="fuel_logs",
        help_text="Fleet vehicle fueled",
    )
    driver = models.ForeignKey(
        "hrm.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_fuel_logs",
        help_text="Driver who performed or authorized the fill-up",
    )
    fuel_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_fuel_sales",
        help_text="Fuel supplier or service station party",
    )
    fuel_date = models.DateTimeField(default=timezone.now)
    odometer_at_fueling = models.PositiveIntegerField(help_text="Odometer reading at time of fill-up")
    fuel_type = models.CharField(max_length=28, choices=FUEL_TYPE_CHOICES, default="regular_gasoline")
    quantity_gallons = models.DecimalField(
        max_digits=9,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Gallons (or kWh for electric vehicles) pumped",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Cost per gallon / unit",
    )
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_fuel_logs",
        help_text="Global transaction currency",
    )
    is_full_tank = models.BooleanField(default=True, help_text="Tank was filled to capacity (required for accurate MPG)")
    fuel_card_token = models.CharField(max_length=64, blank=True, help_text="Masked fuel card or RFID tag identifier")
    fuel_station_name = models.CharField(max_length=120, blank=True)
    station_city_state = models.CharField(max_length=120, blank=True)
    distance_since_last_fuel = models.PositiveIntegerField(null=True, blank=True, help_text="Miles since previous fill-up")
    calculated_mpg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    route_category = models.CharField(max_length=24, choices=ROUTE_CATEGORY_CHOICES, default="mixed_delivery")
    efficiency_rating = models.CharField(max_length=28, choices=EFFICIENCY_RATING_CHOICES, default="optimal")
    receipt_reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-fuel_date", "-number"]
        verbose_name = "Vehicle Fuel Log"
        verbose_name_plural = "Vehicle Fuel Logs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_vful_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "vehicle", "fuel_date"], name="idx_vful_ten_veh_date"),
            models.Index(fields=["tenant", "fuel_date"], name="idx_vful_ten_fdate"),
        ]

    def __str__(self):
        return f"{self.number} — {self.vehicle.name} ({self.fuel_date.strftime('%Y-%m-%d')})"

    def save(self, *args, **kwargs):
        if self.unit_price and self.quantity_gallons and not self.total_cost:
            self.total_cost = (self.quantity_gallons * self.unit_price).quantize(Decimal("0.01"))
        elif self.total_cost and self.quantity_gallons and not self.unit_price:
            self.unit_price = (self.total_cost / self.quantity_gallons).quantize(Decimal("0.001"))

        # Compute MPG from previous log if available
        if self.odometer_at_fueling and self.quantity_gallons and self.is_full_tank:
            prev_log = (
                VehicleFuelLog.objects.filter(
                    tenant=self.tenant,
                    vehicle=self.vehicle,
                    fuel_date__lt=self.fuel_date,
                    odometer_at_fueling__lt=self.odometer_at_fueling,
                )
                .order_by("-fuel_date")
                .first()
            )
            if prev_log and prev_log.odometer_at_fueling:
                dist = self.odometer_at_fueling - prev_log.odometer_at_fueling
                if dist > 0:
                    self.distance_since_last_fuel = dist
                    self.calculated_mpg = (Decimal(dist) / self.quantity_gallons).quantize(Decimal("0.01"))

        # Update vehicle odometer if higher
        if self.vehicle and self.odometer_at_fueling > self.vehicle.current_odometer:
            self.vehicle.current_odometer = self.odometer_at_fueling
            self.vehicle.save(update_fields=["current_odometer", "updated_at"])

        super().save(*args, **kwargs)

    @property
    def efficiency_badge_class(self):
        return self.EFFICIENCY_CSS.get(self.efficiency_rating, "badge-slate")

    @property
    def cost_per_mile(self):
        if self.distance_since_last_fuel and self.total_cost and self.distance_since_last_fuel > 0:
            return (self.total_cost / Decimal(self.distance_since_last_fuel)).quantize(Decimal("0.01"))
        return None
