from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetEnergyReading(TenantNumbered):
    """
    Asset utility energy consumption, peak electric demand, Specific Energy Consumption (SEC)
    intensity metrics, and Scope 1 / Scope 2 greenhouse gas (kg CO2e) emissions ledger [AENG-].
    """

    NUMBER_PREFIX = "AENG"

    UTILITY_TYPE_CHOICES = [
        ("electricity", "Electricity (kWh)"),
        ("natural_gas", "Natural Gas (m3 / MMBtu)"),
        ("diesel", "Diesel Fuel (Liters)"),
        ("heavy_fuel_oil", "Heavy Fuel Oil (Liters)"),
        ("steam", "Steam (Tons)"),
        ("compressed_air", "Compressed Air (Nm3)"),
        ("industrial_water", "Industrial Water (m3)"),
    ]

    GHG_SCOPE_CHOICES = [
        ("scope_1", "Scope 1: Direct Combustion"),
        ("scope_2", "Scope 2: Purchased Electricity/Steam"),
        ("scope_3", "Scope 3: Indirect Value Chain"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("validated", "Validated"),
        ("flagged_anomaly", "Flagged Anomaly / Peak Spike"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "pending": "badge-slate",
        "validated": "badge-green",
        "flagged_anomaly": "badge-red",
        "cancelled": "badge-muted",
    }

    UTILITY_CSS = {
        "electricity": "badge-info",
        "natural_gas": "badge-info",
        "diesel": "badge-amber",
        "heavy_fuel_oil": "badge-slate",
        "steam": "badge-slate",
        "compressed_air": "badge-info",
        "industrial_water": "badge-info",
    }

    GHG_SCOPE_CSS = {
        "scope_1": "badge-amber",
        "scope_2": "badge-info",
        "scope_3": "badge-slate",
    }

    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="energy_readings",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="energy_readings",
        help_text="Operational machinery or meter location",
    )
    reading_timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when meter reading was captured",
    )
    utility_type = models.CharField(
        max_length=25,
        choices=UTILITY_TYPE_CHOICES,
        default="electricity",
        help_text="Energy utility source type",
    )
    meter_serial_number = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hardware smart meter identifier or sub-meter tag",
    )
    consumption_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Metered consumption quantity",
    )
    unit_of_measure = models.CharField(
        max_length=20,
        default="kWh",
        help_text="Unit of measure (e.g. kWh, m3, liters, tons)",
    )
    peak_demand_kw = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peak electrical demand load in kilowatts",
    )
    power_factor = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Power factor cos phi (0.000 to 1.000)",
    )
    operating_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Active run hours during the meter reading window",
    )
    units_produced = models.IntegerField(
        default=0,
        help_text="Output production pieces manufactured during reading period",
    )
    energy_intensity_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Specific Energy Consumption rate per machine hour",
    )
    energy_intensity_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Specific Energy Consumption rate per unit produced",
    )
    emission_factor = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.4500"),
        help_text="Grid emission factor in kg CO2e per utility unit",
    )
    carbon_emissions_kg_co2e = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Calculated greenhouse gas carbon footprint (kg CO2e)",
    )
    ghg_scope = models.CharField(
        max_length=15,
        choices=GHG_SCOPE_CHOICES,
        default="scope_2",
        help_text="GHG Protocol accounting scope",
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Tariff cost per unit of utility consumption",
    )
    total_energy_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total calculated energy expense",
    )
    utility_provider = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="energy_readings",
        help_text="Energy utility contractor or electricity board",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Audit and validation status",
    )
    notes = models.TextField(
        blank=True,
        help_text="Meter audit observations or peak spike explanation",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_energy_readings",
        help_text="Facility engineer or IoT ingestion agent",
    )

    class Meta:
        ordering = ["-reading_timestamp", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aeng_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "reading_timestamp"], name="idx_aeng_ten_time"),
            models.Index(fields=["tenant", "utility_type"], name="idx_aeng_ten_util"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_aeng_ten_fa"),
        ]

    def __str__(self):
        asset_name = ""
        if self.fixed_asset:
            asset_name = f" - {self.fixed_asset.name}"
        elif self.operational_asset:
            asset_name = f" - {self.operational_asset.name}"
        return f"{self.number}{asset_name} ({self.get_utility_type_display()}: {self.consumption_value} {self.unit_of_measure})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def utility_css(self):
        return self.UTILITY_CSS.get(self.utility_type, "badge-slate")

    @property
    def scope_css(self):
        return self.GHG_SCOPE_CSS.get(self.ghg_scope, "badge-slate")

    def calculate_energy_metrics(self):
        # 1. Hourly Intensity (SEC/hr)
        if self.operating_hours and self.operating_hours > 0 and self.consumption_value:
            intensity_hr = self.consumption_value / self.operating_hours
            self.energy_intensity_per_hour = Decimal(str(round(float(intensity_hr), 4)))
        else:
            self.energy_intensity_per_hour = Decimal("0.0000")

        # 2. Per-Unit Intensity (SEC/unit)
        if self.units_produced and self.units_produced > 0 and self.consumption_value:
            intensity_unit = self.consumption_value / Decimal(str(self.units_produced))
            self.energy_intensity_per_unit = Decimal(str(round(float(intensity_unit), 4)))
        else:
            self.energy_intensity_per_unit = Decimal("0.0000")

        # 3. Carbon Emissions (kg CO2e) = Consumption * Emission Factor
        if self.consumption_value and self.emission_factor:
            emissions = self.consumption_value * self.emission_factor
            self.carbon_emissions_kg_co2e = Decimal(str(round(float(emissions), 4)))
        else:
            self.carbon_emissions_kg_co2e = Decimal("0.0000")

        # 4. Total Energy Cost = Consumption * Cost per unit
        if self.consumption_value and self.cost_per_unit:
            cost = self.consumption_value * self.cost_per_unit
            self.total_energy_cost = Decimal(str(round(float(cost), 2)))
        else:
            self.total_energy_cost = Decimal("0.00")

    def save(self, *args, **kwargs):
        self.calculate_energy_metrics()
        super().save(*args, **kwargs)
