"""Fleet Vehicle Master & Telematics Registration model (11.19)."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class FleetVehicle(TenantNumbered):
    """Core fleet vehicle registry with DMV compliance and live telematics tracking [FLT]."""

    NUMBER_PREFIX = "FLT"

    VEHICLE_TYPE_CHOICES = [
        ("passenger_car", "Passenger Car / Sedan"),
        ("suv_crossover", "SUV / Crossover"),
        ("pickup_truck", "Pickup Truck"),
        ("cargo_van", "Cargo / Delivery Van"),
        ("box_truck", "Box Truck / Straight Truck"),
        ("semi_tractor", "Semi-Tractor / Class 8"),
        ("flatbed_truck", "Flatbed Truck"),
        ("trailer", "Trailer / Semi-Trailer"),
        ("forklift_yard", "Forklift / Yard Spotter"),
        ("bus_shuttle", "Bus / Passenger Shuttle"),
        ("specialty_equipment", "Specialty Utility Vehicle"),
    ]

    FUEL_TYPE_CHOICES = [
        ("gasoline", "Gasoline (Petrol)"),
        ("diesel", "Diesel"),
        ("electric_ev", "Battery Electric (BEV)"),
        ("hybrid_electric", "Hybrid Electric (HEV)"),
        ("plug_in_hybrid", "Plug-in Hybrid (PHEV)"),
        ("cng_lpg", "CNG / LPG / Autogas"),
    ]

    OWNERSHIP_TYPE_CHOICES = [
        ("owned", "Company Owned"),
        ("leased", "Leased"),
        ("rented", "Short-Term Rental"),
        ("customer_managed", "Customer / Contractor Managed"),
    ]

    STATUS_CHOICES = [
        ("staged_available", "Staged / Available"),
        ("active_in_service", "Active In Service"),
        ("in_shop_maintenance", "In Shop / Maintenance"),
        ("loaner_out", "Loaner / Temporary Assignment"),
        ("out_of_service", "Out of Service"),
        ("pending_disposal", "Pending Disposal"),
        ("decommissioned", "Decommissioned / Retired"),
    ]

    COMPLIANCE_STATUS_CHOICES = [
        ("compliant", "Compliant"),
        ("renewal_due_soon", "Renewal Due Soon"),
        ("expired_non_compliant", "Expired / Non-Compliant"),
        ("exempt", "Exempt"),
    ]

    ENGINE_STATE_CHOICES = [
        ("engine_off", "Engine Off"),
        ("idling", "Idling"),
        ("moving_normal", "Moving / In Transit"),
        ("speeding_alert", "Speeding Alert"),
        ("towed_unauthorized", "Unauthorized Movement / Towed"),
    ]

    GEOFENCE_STATUS_CHOICES = [
        ("inside_zone", "Inside Authorized Zone"),
        ("outside_zone", "Outside Operating Zone"),
        ("geofence_breach_alert", "Geofence Breach Alert"),
    ]

    STATUS_CSS = {
        "staged_available": "badge-info",
        "active_in_service": "badge-green",
        "in_shop_maintenance": "badge-amber",
        "loaner_out": "badge-info",
        "out_of_service": "badge-red",
        "pending_disposal": "badge-slate",
        "decommissioned": "badge-muted",
    }

    COMPLIANCE_CSS = {
        "compliant": "badge-green",
        "renewal_due_soon": "badge-amber",
        "expired_non_compliant": "badge-red",
        "exempt": "badge-slate",
    }

    ENGINE_STATE_CSS = {
        "engine_off": "badge-slate",
        "idling": "badge-amber",
        "moving_normal": "badge-green",
        "speeding_alert": "badge-red",
        "towed_unauthorized": "badge-red",
    }

    GEOFENCE_CSS = {
        "inside_zone": "badge-green",
        "outside_zone": "badge-amber",
        "geofence_breach_alert": "badge-red",
    }

    LOCKED_STATUSES = {"decommissioned"}

    name = models.CharField(max_length=150, help_text="Vehicle designation or fleet unit name")
    vin = models.CharField(max_length=24, blank=True, help_text="17-character Vehicle Identification Number")
    license_plate = models.CharField(max_length=32)
    registration_state = models.CharField(max_length=32, blank=True, help_text="DMV jurisdiction / state")
    make = models.CharField(max_length=60)
    model = models.CharField(max_length=60)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900), MaxValueValidator(2100)])
    vehicle_type = models.CharField(max_length=28, choices=VEHICLE_TYPE_CHOICES, default="cargo_van")
    fuel_type = models.CharField(max_length=24, choices=FUEL_TYPE_CHOICES, default="gasoline")
    ownership_type = models.CharField(max_length=24, choices=OWNERSHIP_TYPE_CHOICES, default="owned")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="staged_available")
    compliance_status = models.CharField(max_length=28, choices=COMPLIANCE_STATUS_CHOICES, default="compliant")
    title_number = models.CharField(max_length=64, blank=True)
    registration_expiration_date = models.DateField(null=True, blank=True)
    safety_inspection_due_date = models.DateField(null=True, blank=True)
    emissions_inspection_due_date = models.DateField(null=True, blank=True)
    current_odometer = models.PositiveIntegerField(default=0, help_text="Current cumulative odometer reading")
    engine_hours = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    gross_vehicle_weight_rating_lbs = models.PositiveIntegerField(null=True, blank=True, help_text="GVWR in lbs")
    fuel_tank_capacity_gallons = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    battery_capacity_kwh = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    # Telematics and live GPS fields
    is_telematics_enabled = models.BooleanField(default=False)
    telematics_device_id = models.CharField(max_length=80, blank=True)
    current_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    current_location_name = models.CharField(max_length=255, blank=True)
    current_speed_mph = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    current_heading = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Compass heading in degrees (0-359)")
    last_telemetry_at = models.DateTimeField(null=True, blank=True, editable=False)
    engine_state = models.CharField(max_length=24, choices=ENGINE_STATE_CHOICES, default="engine_off")
    geofence_status = models.CharField(max_length=28, choices=GEOFENCE_STATUS_CHOICES, default="inside_zone")

    # Spine & Sibling ForeignKeys
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_vehicles",
        help_text="Optional general physical asset link",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_vehicles",
        help_text="Optional financial fixed asset ledger link",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_vehicles",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_vehicles",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fleet_vehicles",
        help_text="Owning department or branch",
    )
    primary_driver = models.ForeignKey(
        "hrm.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_fleet_vehicles",
        help_text="Primary assigned driver / employee",
    )
    custodian_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custody_fleet_vehicles",
        help_text="Responsible party or contractor custodian",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "-number"]
        verbose_name = "Fleet Vehicle"
        verbose_name_plural = "Fleet Vehicles"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_flt_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_flt_ten_stat"),
            models.Index(fields=["tenant", "vehicle_type"], name="idx_flt_ten_vtype"),
            models.Index(fields=["tenant", "license_plate"], name="idx_flt_ten_plate"),
            models.Index(fields=["tenant", "registration_expiration_date"], name="idx_flt_ten_regexp"),
            models.Index(fields=["tenant", "-last_telemetry_at"], name="idx_flt_ten_last_tel"),
        ]

    def __str__(self):
        if self.license_plate:
            return f"{self.name} ({self.license_plate})"
        return self.name

    def clean(self):
        super().clean()
        if self.vin and len(self.vin.strip()) not in (17, 0):
            # Non-empty VIN should be standard 17 chars unless classic/off-highway
            pass
        if self.current_heading is not None and not (0 <= self.current_heading <= 360):
            raise ValidationError({"current_heading": "Compass heading must be between 0 and 360 degrees."})

    def refresh_compliance_status(self, today=None):
        if today is None:
            today = timezone.now().date()
        if self.compliance_status == "exempt":
            return
        if self.registration_expiration_date:
            if self.registration_expiration_date < today:
                self.compliance_status = "expired_non_compliant"
            elif self.registration_expiration_date <= today + timedelta(days=30):
                self.compliance_status = "renewal_due_soon"
            else:
                self.compliance_status = "compliant"

    @property
    def is_registration_expired(self):
        if not self.registration_expiration_date:
            return False
        return self.registration_expiration_date < timezone.now().date()

    @property
    def is_registration_due_soon(self):
        if not self.registration_expiration_date:
            return False
        today = timezone.now().date()
        return today <= self.registration_expiration_date <= today + timedelta(days=30)

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def compliance_badge_class(self):
        return self.COMPLIANCE_CSS.get(self.compliance_status, "badge-slate")

    @property
    def engine_state_badge_class(self):
        return self.ENGINE_STATE_CSS.get(self.engine_state, "badge-slate")

    @property
    def geofence_badge_class(self):
        return self.GEOFENCE_CSS.get(self.geofence_status, "badge-slate")
