"""HVAC, MEP, Vertical Transport, & Structural Building System model (11.17)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.SpaceFacilityAsset._validators import (
    add_field_error,
    validate_non_negative,
    validate_pct_range,
    validate_tenant_fks,
)


class AssetBuildingSystem(TenantNumbered):
    """HVAC, climate-control, electrical, plumbing, elevator, fire/safety, and structural asset register [AFBS]."""

    NUMBER_PREFIX = "AFBS"

    SYSTEM_DOMAIN_CHOICES = [
        ("hvac_climate", "HVAC & Climate Control"),
        ("electrical_power", "Electrical & Power Distribution"),
        ("plumbing_water", "Plumbing & Water Systems"),
        ("elevator_vertical", "Elevators & Vertical Transport"),
        ("fire_life_safety", "Fire & Life Safety"),
        ("structural_envelope", "Structural & Building Envelope"),
        ("bms_controls", "BMS & Building Controls"),
        ("backup_generation", "Backup Power & Generation"),
    ]

    INFRASTRUCTURE_DOMAINS = (
        "electrical_power",
        "plumbing_water",
        "elevator_vertical",
        "fire_life_safety",
        "structural_envelope",
        "bms_controls",
        "backup_generation",
    )

    SUBSYSTEM_TYPE_CHOICES = [
        ("ahu_air_handler", "Air Handling Unit (AHU)"),
        ("chiller_plant", "Chiller Plant"),
        ("boiler_heating", "Boiler / Heating Plant"),
        ("vav_terminal", "VAV / Fan Coil Terminal"),
        ("rooftop_unit", "Rooftop Package Unit (RTU)"),
        ("switchgear_panel", "Main Switchgear / Panelboard"),
        ("transformer_sub", "Substation Transformer"),
        ("ups_battery", "UPS / Battery Bank"),
        ("generator_set", "Standby Generator Set"),
        ("booster_pump", "Booster / Sump Pump"),
        ("passenger_elevator", "Passenger Elevator"),
        ("freight_elevator", "Freight / Service Elevator"),
        ("sprinkler_riser", "Sprinkler Riser / Suppression"),
        ("fire_alarm_panel", "Fire Alarm Control Panel"),
        ("roof_structural", "Roofing / Structural Framing"),
        ("facade_envelope", "Facade / Building Envelope"),
    ]

    COMFORT_STATUS_CHOICES = [
        ("optimal", "Optimal Comfort Band"),
        ("drift_warning", "Drift Warning"),
        ("out_of_band", "Out of Comfort Band"),
        ("offline", "System Offline"),
        ("not_applicable", "Not Applicable (Non-HVAC)"),
    ]

    CONDITION_GRADE_CHOICES = [
        ("excellent", "A — Excellent"),
        ("good", "B — Good"),
        ("fair", "C — Fair"),
        ("poor", "D — Poor"),
        ("critical", "F — Critical"),
    ]

    CRITICALITY_TIER_CHOICES = [
        ("tier_1_life_safety", "Tier 1 — Life Safety"),
        ("tier_2_mission_crit", "Tier 2 — Mission Critical"),
        ("tier_3_operational", "Tier 3 — Operational"),
        ("tier_4_standard", "Tier 4 — Standard"),
    ]

    STATUS_CHOICES = [
        ("operational", "Operational"),
        ("degraded", "Degraded"),
        ("under_maintenance", "Under Maintenance"),
        ("standby", "Standby"),
        ("decommissioned", "Decommissioned"),
    ]

    STATUS_CSS = {
        "operational": "badge-green",
        "degraded": "badge-amber",
        "under_maintenance": "badge-info",
        "standby": "badge-slate",
        "decommissioned": "badge-muted",
    }

    COMFORT_CSS = {
        "optimal": "badge-green",
        "drift_warning": "badge-amber",
        "out_of_band": "badge-red",
        "offline": "badge-muted",
        "not_applicable": "badge-slate",
    }

    CONDITION_CSS = {
        "excellent": "badge-green",
        "good": "badge-info",
        "fair": "badge-amber",
        "poor": "badge-red",
        "critical": "badge-red",
    }

    CRITICALITY_CSS = {
        "tier_1_life_safety": "badge-red",
        "tier_2_mission_crit": "badge-amber",
        "tier_3_operational": "badge-info",
        "tier_4_standard": "badge-slate",
    }

    LOCKED_STATUSES = {"decommissioned"}

    _TENANT_FK_FIELDS = (
        "facility_space",
        "operational_asset",
        "fixed_asset",
        "latest_energy_reading",
        "maintenance_schedule",
        "operating_permit",
        "schematic_document",
        "service_vendor",
        "org_unit",
    )

    name = models.CharField(max_length=200)
    system_domain = models.CharField(
        max_length=32, choices=SYSTEM_DOMAIN_CHOICES, default="hvac_climate"
    )
    subsystem_type = models.CharField(
        max_length=32, choices=SUBSYSTEM_TYPE_CHOICES, default="ahu_air_handler"
    )
    facility_space = models.ForeignKey(
        "assets.AssetFacilitySpace",
        on_delete=models.PROTECT,
        related_name="building_systems",
    )
    pin_x_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    pin_y_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    manufacturer = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=80, blank=True)
    serial_number = models.CharField(max_length=80, blank=True)
    load_or_voltage_rating = models.CharField(max_length=80, blank=True)
    ashrae_nfpa_code_ref = models.CharField(max_length=80, blank=True)

    served_area_sqft = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    design_capacity_btu_kw = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    refrigerant_type = models.CharField(max_length=40, blank=True)
    setpoint_temp_c = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    measured_temp_c = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    target_humidity_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    measured_humidity_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    airflow_cfm = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    energy_efficiency_rating = models.CharField(max_length=40, blank=True)
    comfort_status = models.CharField(
        max_length=24,
        choices=COMFORT_STATUS_CHOICES,
        default="not_applicable",
        editable=False,
    )

    condition_grade = models.CharField(
        max_length=20, choices=CONDITION_GRADE_CHOICES, default="good"
    )
    criticality_tier = models.CharField(
        max_length=28, choices=CRITICALITY_TIER_CHOICES, default="tier_3_operational"
    )
    remaining_useful_life_years = models.PositiveSmallIntegerField(null=True, blank=True)
    replacement_cost_estimate = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00")
    )
    last_statutory_inspection_date = models.DateField(null=True, blank=True)
    next_inspection_due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="operational",
        editable=False,
    )

    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    latest_energy_reading = models.ForeignKey(
        "assets.AssetEnergyReading",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    maintenance_schedule = models.ForeignKey(
        "assets.AssetMaintenanceSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    operating_permit = models.ForeignKey(
        "assets.AssetPermitLicense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    schematic_document = models.ForeignKey(
        "assets.AssetDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    service_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serviced_building_systems",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="building_systems",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["system_domain", "name", "-number"]
        verbose_name = "Building System"
        verbose_name_plural = "Building Systems"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_afbs_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_afbs_ten_stat"),
            models.Index(fields=["tenant", "system_domain"], name="idx_afbs_ten_dom"),
            models.Index(fields=["tenant", "subsystem_type"], name="idx_afbs_ten_sub"),
            models.Index(fields=["tenant", "comfort_status"], name="idx_afbs_ten_cmf"),
            models.Index(fields=["tenant", "condition_grade"], name="idx_afbs_ten_cond"),
            models.Index(fields=["tenant", "criticality_tier"], name="idx_afbs_ten_crit"),
            models.Index(fields=["tenant", "facility_space"], name="idx_afbs_ten_spc"),
            models.Index(fields=["tenant", "next_inspection_due_date"], name="idx_afbs_ten_insp"),
        ]

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    @property
    def is_inspection_overdue(self):
        return bool(
            self.next_inspection_due_date
            and self.status != "decommissioned"
            and self.next_inspection_due_date < timezone.now().date()
        )

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def comfort_badge_class(self):
        return self.COMFORT_CSS.get(self.comfort_status, "badge-slate")

    @property
    def condition_badge_class(self):
        return self.CONDITION_CSS.get(self.condition_grade, "badge-slate")

    @property
    def criticality_badge_class(self):
        return self.CRITICALITY_CSS.get(self.criticality_tier, "badge-slate")

    def compute_comfort_status(self):
        if self.status in ("under_maintenance", "decommissioned", "standby"):
            return "offline"
        has_temp = self.setpoint_temp_c is not None and self.measured_temp_c is not None
        has_hum = self.target_humidity_pct is not None and self.measured_humidity_pct is not None
        if self.system_domain not in ("hvac_climate", "bms_controls") and not (has_temp or has_hum):
            return "not_applicable"
        if not (has_temp or has_hum):
            return "not_applicable"

        worst = "optimal"
        if has_temp:
            temp_diff = abs(self.measured_temp_c - self.setpoint_temp_c)
            if temp_diff > Decimal("2.50"):
                return "out_of_band"
            if temp_diff > Decimal("1.00"):
                worst = "drift_warning"
        if has_hum:
            hum_diff = abs(self.measured_humidity_pct - self.target_humidity_pct)
            if hum_diff > Decimal("10.00"):
                return "out_of_band"
            if hum_diff > Decimal("5.00"):
                worst = "drift_warning"
        return worst

    def clean(self):
        super().clean()
        errors = {}
        if self.tenant_id:
            validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)

        validate_pct_range(self.pin_x_pct, errors, "pin_x_pct", "Pin X %")
        validate_pct_range(self.pin_y_pct, errors, "pin_y_pct", "Pin Y %")
        validate_pct_range(self.target_humidity_pct, errors, "target_humidity_pct", "Target humidity %")
        validate_pct_range(self.measured_humidity_pct, errors, "measured_humidity_pct", "Measured humidity %")
        validate_non_negative(self.served_area_sqft, errors, "served_area_sqft", "Served area")
        validate_non_negative(self.design_capacity_btu_kw, errors, "design_capacity_btu_kw", "Design capacity")
        validate_non_negative(self.airflow_cfm, errors, "airflow_cfm", "Airflow CFM")
        validate_non_negative(
            self.replacement_cost_estimate,
            errors,
            "replacement_cost_estimate",
            "Replacement cost estimate",
        )
        if (
            self.last_statutory_inspection_date
            and self.next_inspection_due_date
            and self.next_inspection_due_date < self.last_statutory_inspection_date
        ):
            add_field_error(
                errors,
                "next_inspection_due_date",
                "Next inspection due date cannot precede the last statutory inspection date.",
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.comfort_status = self.compute_comfort_status()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} — {self.name}"
