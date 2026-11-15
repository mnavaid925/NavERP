"""
Unit tests for Module 11.19: Fleet & Vehicle Management Models.
Covers FleetVehicle [FLT-], VehicleFuelLog [VFUL-],
VehicleDriverAssignment [VDRV-], VehicleServiceSchedule [VSRV-],
auto-numbering, constraints, validations, badge classes, derived metrics,
MPG calculation, compliance and qualification workflows, and multi-tenancy isolation.
"""

from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    FleetVehicle,
    VehicleFuelLog,
    VehicleDriverAssignment,
    VehicleServiceSchedule,
)

pytestmark = pytest.mark.django_db

_FLEETVEHICLE_VALID_BADGE_CLASSES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
}


# =====================================================================
# Module-level Helpers (Must start with _fleetvehicle_*)
# =====================================================================


def _fleetvehicle_create_vehicle(tenant, name="Van 200", **kwargs):
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "name": name,
        "vin": "1FTNE3Y89PKB99999",
        "license_plate": "TEST-200",
        "registration_state": "CA",
        "registration_expiration_date": today + timedelta(days=180),
        "safety_inspection_due_date": today + timedelta(days=120),
        "make": "Ford",
        "model": "Transit",
        "year": 2023,
        "vehicle_type": "cargo_van",
        "fuel_type": "gasoline",
        "ownership_type": "owned",
        "status": "active_in_service",
        "compliance_status": "compliant",
        "current_odometer": 10000,
        "engine_hours": Decimal("500.00"),
    }
    data.update(kwargs)
    return FleetVehicle.objects.create(**data)


def _fleetvehicle_create_fuel_log(tenant, vehicle, **kwargs):
    now = timezone.now()
    data = {
        "tenant": tenant,
        "vehicle": vehicle,
        "fuel_date": now,
        "odometer_at_fueling": 10500,
        "fuel_type": "regular_gasoline",
        "quantity_gallons": Decimal("20.000"),
        "unit_price": Decimal("4.000"),
        "total_cost": Decimal("80.00"),
        "is_full_tank": True,
    }
    data.update(kwargs)
    return VehicleFuelLog.objects.create(**data)


def _fleetvehicle_create_assignment(tenant, vehicle, driver, **kwargs):
    now = timezone.now()
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "vehicle": vehicle,
        "driver": driver,
        "assignment_role": "primary_assigned",
        "status": "active",
        "start_datetime": now - timedelta(days=2),
        "start_odometer": 10000,
        "driver_license_number": "DL-12345",
        "driver_license_state": "CA",
        "license_class": "standard_non_cdl",
        "license_expiration_date": today + timedelta(days=365),
        "medical_card_expiration_date": today + timedelta(days=365),
        "safety_score": 95,
        "duty_status": "driving",
    }
    data.update(kwargs)
    return VehicleDriverAssignment.objects.create(**data)


def _fleetvehicle_create_service_schedule(tenant, vehicle, **kwargs):
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "vehicle": vehicle,
        "service_title": "Routine Oil Change",
        "service_type": "engine_oil_filter",
        "interval_mileage": 5000,
        "interval_months": 6,
        "last_service_date": today - timedelta(days=90),
        "last_service_odometer": 5000,
        "next_due_date": today + timedelta(days=90),
        "next_due_odometer": 10000,
        "priority": "scheduled_pm",
        "status": "active_tracking",
        "estimated_cost": Decimal("150.00"),
    }
    data.update(kwargs)
    return VehicleServiceSchedule.objects.create(**data)


# =====================================================================
# 1. FleetVehicle Master Tests
# =====================================================================


def test_fleetvehicle_model_auto_numbering_and_prefix(tenant_a, fleet_vehicle_a):
    assert fleet_vehicle_a.number.startswith("FLT-")
    assert fleet_vehicle_a.number == "FLT-00001"

    second_veh = _fleetvehicle_create_vehicle(tenant_a, name="Fleet Van 102", license_plate="VAN-102")
    assert second_veh.number == "FLT-00002"

    custom_veh = _fleetvehicle_create_vehicle(
        tenant_a, name="Fleet Custom", number="FLT-99999", license_plate="VAN-999"
    )
    assert custom_veh.number == "FLT-99999"


def test_fleetvehicle_model_str_representation(tenant_a, fleet_vehicle_a):
    assert str(fleet_vehicle_a) == f"{fleet_vehicle_a.name} ({fleet_vehicle_a.license_plate})"

    no_plate_veh = _fleetvehicle_create_vehicle(tenant_a, name="Yard Spotter 01", license_plate="")
    assert str(no_plate_veh) == "Yard Spotter 01"


def test_fleetvehicle_model_choices_and_constants():
    vehicle_types = dict(FleetVehicle.VEHICLE_TYPE_CHOICES)
    assert "cargo_van" in vehicle_types
    assert "semi_tractor" in vehicle_types
    assert "passenger_car" in vehicle_types

    fuel_types = dict(FleetVehicle.FUEL_TYPE_CHOICES)
    assert "gasoline" in fuel_types
    assert "diesel" in fuel_types
    assert "electric_ev" in fuel_types

    ownership_types = dict(FleetVehicle.OWNERSHIP_TYPE_CHOICES)
    assert "owned" in ownership_types
    assert "leased" in ownership_types

    statuses = dict(FleetVehicle.STATUS_CHOICES)
    assert "staged_available" in statuses
    assert "active_in_service" in statuses
    assert "decommissioned" in statuses

    compliance_statuses = dict(FleetVehicle.COMPLIANCE_STATUS_CHOICES)
    assert "compliant" in compliance_statuses
    assert "renewal_due_soon" in compliance_statuses
    assert "expired_non_compliant" in compliance_statuses
    assert "exempt" in compliance_statuses

    engine_states = dict(FleetVehicle.ENGINE_STATE_CHOICES)
    assert "engine_off" in engine_states
    assert "moving_normal" in engine_states
    assert "speeding_alert" in engine_states

    geofence_statuses = dict(FleetVehicle.GEOFENCE_STATUS_CHOICES)
    assert "inside_zone" in geofence_statuses
    assert "geofence_breach_alert" in geofence_statuses


def test_fleetvehicle_model_badge_properties(fleet_vehicle_a):
    for status_key, expected_badge in FleetVehicle.STATUS_CSS.items():
        fleet_vehicle_a.status = status_key
        assert fleet_vehicle_a.status_badge_class == expected_badge
        assert fleet_vehicle_a.status_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for comp_key, expected_badge in FleetVehicle.COMPLIANCE_CSS.items():
        fleet_vehicle_a.compliance_status = comp_key
        assert fleet_vehicle_a.compliance_badge_class == expected_badge
        assert fleet_vehicle_a.compliance_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for eng_key, expected_badge in FleetVehicle.ENGINE_STATE_CSS.items():
        fleet_vehicle_a.engine_state = eng_key
        assert fleet_vehicle_a.engine_state_badge_class == expected_badge
        assert fleet_vehicle_a.engine_state_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for geo_key, expected_badge in FleetVehicle.GEOFENCE_CSS.items():
        fleet_vehicle_a.geofence_status = geo_key
        assert fleet_vehicle_a.geofence_badge_class == expected_badge
        assert fleet_vehicle_a.geofence_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    fleet_vehicle_a.status = "unknown_status"
    assert fleet_vehicle_a.status_badge_class == "badge-slate"


def test_fleetvehicle_model_clean_validation(tenant_a):
    # Year validation: MinValueValidator(1900), MaxValueValidator(2100)
    low_year = FleetVehicle(
        tenant=tenant_a,
        name="Antique Van",
        make="Ford",
        model="Model T",
        year=1899,
        license_plate="ANT-1899",
    )
    with pytest.raises(ValidationError) as exc_low:
        low_year.full_clean()
    assert "year" in exc_low.value.message_dict

    high_year = FleetVehicle(
        tenant=tenant_a,
        name="Future Van",
        make="Tesla",
        model="Cybertruck 3",
        year=2101,
        license_plate="FUT-2101",
    )
    with pytest.raises(ValidationError) as exc_high:
        high_year.full_clean()
    assert "year" in exc_high.value.message_dict

    # Heading validation: 0 <= current_heading <= 360
    invalid_heading = FleetVehicle(
        tenant=tenant_a,
        name="Heading Error Van",
        make="Ford",
        model="Transit",
        year=2023,
        license_plate="HDG-ERR",
        current_heading=400,
    )
    with pytest.raises(ValidationError) as exc_hdg:
        invalid_heading.full_clean()
    assert "current_heading" in exc_hdg.value.message_dict

    # Valid heading passes
    valid_heading = FleetVehicle(
        tenant=tenant_a,
        name="Valid Heading Van",
        make="Ford",
        model="Transit",
        year=2023,
        license_plate="HDG-OK",
        current_heading=360,
    )
    valid_heading.full_clean()


def test_fleetvehicle_model_refresh_compliance_status_and_properties(tenant_a):
    today = timezone.localdate()
    veh = _fleetvehicle_create_vehicle(tenant_a, name="Compliance Van")

    # Compliant: > 30 days
    veh.registration_expiration_date = today + timedelta(days=45)
    veh.refresh_compliance_status(today=today)
    assert veh.compliance_status == "compliant"
    assert veh.is_registration_expired is False
    assert veh.is_registration_due_soon is False

    # Renewal due soon: <= 30 days and >= today
    veh.registration_expiration_date = today + timedelta(days=20)
    veh.refresh_compliance_status(today=today)
    assert veh.compliance_status == "renewal_due_soon"
    assert veh.is_registration_expired is False
    assert veh.is_registration_due_soon is True

    # Renewal due today
    veh.registration_expiration_date = today
    veh.refresh_compliance_status(today=today)
    assert veh.compliance_status == "renewal_due_soon"
    assert veh.is_registration_expired is False
    assert veh.is_registration_due_soon is True

    # Expired / non-compliant: < today
    veh.registration_expiration_date = today - timedelta(days=1)
    veh.refresh_compliance_status(today=today)
    assert veh.compliance_status == "expired_non_compliant"
    assert veh.is_registration_expired is True
    assert veh.is_registration_due_soon is False

    # Exempt vehicles stay exempt
    veh.compliance_status = "exempt"
    veh.registration_expiration_date = today - timedelta(days=100)
    veh.refresh_compliance_status(today=today)
    assert veh.compliance_status == "exempt"

    # None expiration date properties
    veh.registration_expiration_date = None
    assert veh.is_registration_expired is False
    assert veh.is_registration_due_soon is False


def test_fleetvehicle_model_is_locked_property(fleet_vehicle_a):
    assert fleet_vehicle_a.is_locked is False

    fleet_vehicle_a.status = "decommissioned"
    assert fleet_vehicle_a.is_locked is True

    fleet_vehicle_a.status = "out_of_service"
    assert fleet_vehicle_a.is_locked is False


# =====================================================================
# 2. VehicleFuelLog Tests
# =====================================================================


def test_fleetvehicle_model_fuel_log_auto_numbering_and_str(tenant_a, fleet_vehicle_a, fuel_log_a):
    assert fuel_log_a.number.startswith("VFUL-")
    assert fuel_log_a.number == "VFUL-00001"

    second_log = _fleetvehicle_create_fuel_log(tenant_a, fleet_vehicle_a, odometer_at_fueling=42500)
    assert second_log.number == "VFUL-00002"

    expected_str = f"{fuel_log_a.number} — {fleet_vehicle_a.name} ({fuel_log_a.fuel_date.strftime('%Y-%m-%d')})"
    assert str(fuel_log_a) == expected_str


def test_fleetvehicle_model_fuel_log_cost_and_price_auto_calc(tenant_a, fleet_vehicle_a):
    # Auto-calculate total_cost when unit_price & quantity_gallons provided
    log1 = VehicleFuelLog(
        tenant=tenant_a,
        vehicle=fleet_vehicle_a,
        odometer_at_fueling=43000,
        quantity_gallons=Decimal("15.500"),
        unit_price=Decimal("4.250"),
    )
    log1.save()
    assert log1.total_cost == Decimal("65.88")  # 15.500 * 4.250 = 65.875 -> 65.88

    # Auto-calculate unit_price when total_cost & quantity_gallons provided
    log2 = VehicleFuelLog(
        tenant=tenant_a,
        vehicle=fleet_vehicle_a,
        odometer_at_fueling=43300,
        quantity_gallons=Decimal("20.000"),
        total_cost=Decimal("90.00"),
    )
    log2.save()
    assert log2.unit_price == Decimal("4.500")


def test_fleetvehicle_model_fuel_log_mpg_and_efficiency_calculation(tenant_a):
    vehicle = _fleetvehicle_create_vehicle(tenant_a, name="MPG Test Van", current_odometer=10000)
    base_time = timezone.now() - timedelta(days=10)

    # Initial log at 10,000 miles (no previous log -> no MPG)
    log0 = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time,
        odometer_at_fueling=10000,
        quantity_gallons=Decimal("20.000"),
        unit_price=Decimal("4.000"),
        is_full_tank=True,
    )
    assert log0.distance_since_last_fuel is None
    assert log0.calculated_mpg is None

    # Log 1: distance = 500 miles, 20 gallons -> 25.00 MPG (>= 22.0) -> 'optimal'
    log1 = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time + timedelta(days=2),
        odometer_at_fueling=10500,
        quantity_gallons=Decimal("20.000"),
        unit_price=Decimal("4.000"),
        is_full_tank=True,
    )
    assert log1.distance_since_last_fuel == 500
    assert log1.calculated_mpg == Decimal("25.00")
    assert log1.efficiency_rating == "optimal"

    # Log 2: distance = 360 miles, 20 gallons -> 18.00 MPG (>= 14.0) -> 'acceptable'
    log2 = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time + timedelta(days=4),
        odometer_at_fueling=10860,
        quantity_gallons=Decimal("20.000"),
        unit_price=Decimal("4.000"),
        is_full_tank=True,
    )
    assert log2.distance_since_last_fuel == 360
    assert log2.calculated_mpg == Decimal("18.00")
    assert log2.efficiency_rating == "acceptable"

    # Log 3: distance = 200 miles, 20 gallons -> 10.00 MPG (>= 8.0) -> 'excessive_consumption'
    log3 = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time + timedelta(days=6),
        odometer_at_fueling=11060,
        quantity_gallons=Decimal("20.000"),
        unit_price=Decimal("4.000"),
        is_full_tank=True,
    )
    assert log3.distance_since_last_fuel == 200
    assert log3.calculated_mpg == Decimal("10.00")
    assert log3.efficiency_rating == "excessive_consumption"

    # Log 4: distance = 100 miles, 20 gallons -> 5.00 MPG (< 8.0) -> 'anomalous'
    log4 = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time + timedelta(days=8),
        odometer_at_fueling=11160,
        quantity_gallons=Decimal("20.000"),
        unit_price=Decimal("4.000"),
        is_full_tank=True,
    )
    assert log4.distance_since_last_fuel == 100
    assert log4.calculated_mpg == Decimal("5.00")
    assert log4.efficiency_rating == "anomalous"

    # Log 5: Unrealistic MPG > 120 for non-EV -> 'anomalous'
    log5 = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time + timedelta(days=10),
        odometer_at_fueling=14160,  # 3000 miles on 20 gallons = 150 MPG
        quantity_gallons=Decimal("20.000"),
        unit_price=Decimal("4.000"),
        fuel_type="regular_gasoline",
        is_full_tank=True,
    )
    assert log5.distance_since_last_fuel == 3000
    assert log5.calculated_mpg == Decimal("150.00")
    assert log5.efficiency_rating == "anomalous"

    # Partial tank fill-up does not calculate MPG
    log_partial = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=vehicle,
        fuel_date=base_time + timedelta(days=11),
        odometer_at_fueling=14300,
        quantity_gallons=Decimal("5.000"),
        unit_price=Decimal("4.000"),
        is_full_tank=False,
    )
    assert log_partial.calculated_mpg is None


def test_fleetvehicle_model_fuel_log_vehicle_odometer_update(tenant_a):
    veh = _fleetvehicle_create_vehicle(tenant_a, name="Odo Van", current_odometer=20000)

    # Logging higher odometer updates vehicle
    _fleetvehicle_create_fuel_log(tenant_a, veh, odometer_at_fueling=20500)
    veh.refresh_from_db()
    assert veh.current_odometer == 20500

    # Logging lower odometer does NOT decrease vehicle odometer
    _fleetvehicle_create_fuel_log(tenant_a, veh, odometer_at_fueling=20300)
    veh.refresh_from_db()
    assert veh.current_odometer == 20500


def test_fleetvehicle_model_fuel_log_cost_per_mile_and_badges(tenant_a, fleet_vehicle_a):
    log = _fleetvehicle_create_fuel_log(
        tenant_a,
        fleet_vehicle_a,
        odometer_at_fueling=43000,
        total_cost=Decimal("100.00"),
        distance_since_last_fuel=200,
        efficiency_rating="optimal",
    )
    assert log.cost_per_mile == Decimal("0.50")
    assert log.efficiency_badge_class == "badge-green"

    log.efficiency_rating = "acceptable"
    assert log.efficiency_badge_class == "badge-info"
    log.efficiency_rating = "excessive_consumption"
    assert log.efficiency_badge_class == "badge-amber"
    log.efficiency_rating = "anomalous"
    assert log.efficiency_badge_class == "badge-red"

    # Zero or None distance returns None cost_per_mile
    log.distance_since_last_fuel = None
    assert log.cost_per_mile is None


# =====================================================================
# 3. VehicleDriverAssignment Tests
# =====================================================================


def test_fleetvehicle_model_driver_assignment_auto_numbering_and_str(
    tenant_a, fleet_vehicle_a, driver_profile_a, driver_assignment_a
):
    assert driver_assignment_a.number.startswith("VDRV-")
    assert driver_assignment_a.number == "VDRV-00001"

    second_assign = _fleetvehicle_create_assignment(tenant_a, fleet_vehicle_a, driver_profile_a)
    assert second_assign.number == "VDRV-00002"

    expected_str = f"{driver_assignment_a.number} — {driver_assignment_a.driver} -> {fleet_vehicle_a.name}"
    assert str(driver_assignment_a) == expected_str


def test_fleetvehicle_model_driver_assignment_clean_validation(
    tenant_a, fleet_vehicle_a, driver_profile_a
):
    now = timezone.now()

    # Inverted datetimes: end_datetime < start_datetime
    bad_time = VehicleDriverAssignment(
        tenant=tenant_a,
        vehicle=fleet_vehicle_a,
        driver=driver_profile_a,
        start_datetime=now,
        end_datetime=now - timedelta(hours=2),
    )
    with pytest.raises(ValidationError) as exc_time:
        bad_time.clean()
    assert "end_datetime" in exc_time.value.message_dict

    # Inverted odometer: end_odometer < start_odometer
    bad_odo = VehicleDriverAssignment(
        tenant=tenant_a,
        vehicle=fleet_vehicle_a,
        driver=driver_profile_a,
        start_datetime=now,
        start_odometer=50000,
        end_odometer=49000,
    )
    with pytest.raises(ValidationError) as exc_odo:
        bad_odo.clean()
    assert "end_odometer" in exc_odo.value.message_dict


def test_fleetvehicle_model_driver_assignment_qualification_status(
    tenant_a, fleet_vehicle_a, driver_profile_a
):
    today = timezone.localdate()
    assign = _fleetvehicle_create_assignment(tenant_a, fleet_vehicle_a, driver_profile_a)

    # Qualified: both > 30 days away
    assign.license_expiration_date = today + timedelta(days=60)
    assign.medical_card_expiration_date = today + timedelta(days=90)
    assign.refresh_qualification_status(today=today)
    assert assign.qualification_status == "qualified"
    assert assign.is_license_expired is False
    assert assign.is_license_expiring_soon is False
    assert assign.is_medical_expired is False

    # Expiring soon: license <= 30 days
    assign.license_expiration_date = today + timedelta(days=15)
    assign.refresh_qualification_status(today=today)
    assert assign.qualification_status == "expiring_soon"
    assert assign.is_license_expiring_soon is True
    assert assign.is_license_expired is False

    # Expired / disqualified: license < today
    assign.license_expiration_date = today - timedelta(days=1)
    assign.refresh_qualification_status(today=today)
    assert assign.qualification_status == "expired_disqualified"
    assert assign.is_license_expired is True

    # Expired medical card triggers disqualified
    assign.license_expiration_date = today + timedelta(days=100)
    assign.medical_card_expiration_date = today - timedelta(days=5)
    assign.refresh_qualification_status(today=today)
    assert assign.qualification_status == "expired_disqualified"
    assert assign.is_medical_expired is True

    # Suspended standing remains suspended
    assign.qualification_status = "suspended"
    assign.license_expiration_date = today + timedelta(days=200)
    assign.medical_card_expiration_date = today + timedelta(days=200)
    assign.refresh_qualification_status(today=today)
    assert assign.qualification_status == "suspended"


def test_fleetvehicle_model_driver_assignment_safety_tier(
    tenant_a, fleet_vehicle_a, driver_profile_a
):
    assign = _fleetvehicle_create_assignment(
        tenant_a, fleet_vehicle_a, driver_profile_a, safety_score=95
    )
    assign.refresh_safety_tier()
    assert assign.safety_tier == "exemplary"

    assign.safety_score = 85
    assign.refresh_safety_tier()
    assert assign.safety_tier == "good"

    assign.safety_score = 75
    assign.refresh_safety_tier()
    assert assign.safety_tier == "needs_coaching"

    assign.safety_score = 50
    assign.refresh_safety_tier()
    assert assign.safety_tier == "high_risk"

    # Verify save() triggers refresh_safety_tier & refresh_qualification_status
    assign.safety_score = 92
    assign.save()
    assert assign.safety_tier == "exemplary"


def test_fleetvehicle_model_driver_assignment_badges_and_helpers(driver_assignment_a):
    for status_key, expected_badge in VehicleDriverAssignment.STATUS_CSS.items():
        driver_assignment_a.status = status_key
        assert driver_assignment_a.status_badge_class == expected_badge
        assert driver_assignment_a.status_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for qual_key, expected_badge in VehicleDriverAssignment.QUALIFICATION_CSS.items():
        driver_assignment_a.qualification_status = qual_key
        assert driver_assignment_a.qualification_badge_class == expected_badge
        assert driver_assignment_a.qualification_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for tier_key, expected_badge in VehicleDriverAssignment.SAFETY_TIER_CSS.items():
        driver_assignment_a.safety_tier = tier_key
        assert driver_assignment_a.safety_tier_badge_class == expected_badge
        assert driver_assignment_a.safety_tier_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for duty_key, expected_badge in VehicleDriverAssignment.DUTY_STATUS_CSS.items():
        driver_assignment_a.duty_status = duty_key
        assert driver_assignment_a.duty_status_badge_class == expected_badge
        assert driver_assignment_a.duty_status_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES


# =====================================================================
# 4. VehicleServiceSchedule Tests
# =====================================================================


def test_fleetvehicle_model_service_schedule_auto_numbering_and_str(
    tenant_a, fleet_vehicle_a, service_schedule_a
):
    assert service_schedule_a.number.startswith("VSRV-")
    assert service_schedule_a.number == "VSRV-00001"

    second_srv = _fleetvehicle_create_service_schedule(tenant_a, fleet_vehicle_a)
    assert second_srv.number == "VSRV-00002"

    expected_str = f"{service_schedule_a.number} — {service_schedule_a.service_title} ({fleet_vehicle_a.name})"
    assert str(service_schedule_a) == expected_str


def test_fleetvehicle_model_service_schedule_refresh_status_logic(tenant_a):
    today = timezone.localdate()
    veh = _fleetvehicle_create_vehicle(tenant_a, name="Service Test Van", current_odometer=40000)

    srv = _fleetvehicle_create_service_schedule(
        tenant_a,
        veh,
        next_due_date=today + timedelta(days=60),
        next_due_odometer=45000,
        status="active_tracking",
    )

    # Active tracking (not overdue and not due soon)
    srv.refresh_status(today=today)
    assert srv.status == "active_tracking"
    assert srv.is_overdue is False
    assert srv.is_due_soon is False

    # Date overdue (< today)
    srv.next_due_date = today - timedelta(days=1)
    srv.refresh_status(today=today)
    assert srv.status == "overdue"
    assert srv.is_overdue is True

    # Reset date, make odometer overdue (current_odometer >= next_due_odometer)
    srv.next_due_date = today + timedelta(days=30)
    srv.next_due_odometer = 40000  # veh.current_odometer is 40000
    srv.refresh_status(today=today)
    assert srv.status == "overdue"
    assert srv.is_overdue is True

    # Date due soon (<= 14 days)
    srv.next_due_odometer = 50000
    srv.next_due_date = today + timedelta(days=7)
    srv.refresh_status(today=today)
    assert srv.status == "due_soon"
    assert srv.is_due_soon is True
    assert srv.is_overdue is False

    # Odometer due soon (within 500 miles: 40000 vs 40300)
    srv.next_due_date = today + timedelta(days=60)
    srv.next_due_odometer = 40300
    srv.refresh_status(today=today)
    assert srv.status == "due_soon"
    assert srv.is_due_soon is True
    assert srv.is_overdue is False

    # In-service, paused, completed are locked from auto-refresh
    for locked_status in ("in_service", "paused", "completed"):
        srv.status = locked_status
        srv.next_due_date = today - timedelta(days=30)  # overdue date
        srv.refresh_status(today=today)
        assert srv.status == locked_status


def test_fleetvehicle_model_service_schedule_complete_service(tenant_a):
    today = timezone.localdate()
    veh = _fleetvehicle_create_vehicle(tenant_a, name="Completion Van", current_odometer=40000)
    srv = _fleetvehicle_create_service_schedule(
        tenant_a,
        veh,
        interval_months=6,
        interval_mileage=5000,
        status="overdue",
    )

    completion_date = today
    srv.complete_service(
        completion_date=completion_date,
        odometer=40500,
        cost=Decimal("220.50"),
        notes="Replaced oil filter and fresh synthetic fluid.",
    )
    srv.refresh_from_db()

    assert srv.last_service_date == completion_date
    assert srv.last_service_odometer == 40500
    assert srv.actual_cost == Decimal("220.50")
    assert srv.technician_resolution_notes == "Replaced oil filter and fresh synthetic fluid."
    assert srv.next_due_date == completion_date + timedelta(days=180)  # 6 * 30 days
    assert srv.next_due_odometer == 45500  # 40500 + 5000
    assert srv.status == "active_tracking"


def test_fleetvehicle_model_service_schedule_badges_and_choices(service_schedule_a):
    for status_key, expected_badge in VehicleServiceSchedule.STATUS_CSS.items():
        service_schedule_a.status = status_key
        assert service_schedule_a.status_badge_class == expected_badge
        assert service_schedule_a.status_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    for priority_key, expected_badge in VehicleServiceSchedule.PRIORITY_CSS.items():
        service_schedule_a.priority = priority_key
        assert service_schedule_a.priority_badge_class == expected_badge
        assert service_schedule_a.priority_badge_class in _FLEETVEHICLE_VALID_BADGE_CLASSES

    service_types = dict(VehicleServiceSchedule.SERVICE_TYPE_CHOICES)
    assert "engine_oil_filter" in service_types
    assert "annual_dot_inspection" in service_types
    assert "wheel_alignment" in service_types


# =====================================================================
# 5. Multi-tenancy Isolation & Database Constraints
# =====================================================================


def test_fleetvehicle_model_multitenancy_isolation(
    tenant_a,
    tenant_b,
    fleet_vehicle_a,
    fleet_vehicle_b,
    fuel_log_a,
    fuel_log_b,
    driver_assignment_a,
    driver_assignment_b,
    service_schedule_a,
    service_schedule_b,
):
    # FleetVehicle
    a_vehicles = list(FleetVehicle.objects.filter(tenant=tenant_a))
    assert fleet_vehicle_a in a_vehicles
    assert fleet_vehicle_b not in a_vehicles

    b_vehicles = list(FleetVehicle.objects.filter(tenant=tenant_b))
    assert fleet_vehicle_b in b_vehicles
    assert fleet_vehicle_a not in b_vehicles

    # VehicleFuelLog
    a_logs = list(VehicleFuelLog.objects.filter(tenant=tenant_a))
    assert fuel_log_a in a_logs
    assert fuel_log_b not in a_logs

    b_logs = list(VehicleFuelLog.objects.filter(tenant=tenant_b))
    assert fuel_log_b in b_logs
    assert fuel_log_a not in b_logs

    # VehicleDriverAssignment
    a_assigns = list(VehicleDriverAssignment.objects.filter(tenant=tenant_a))
    assert driver_assignment_a in a_assigns
    assert driver_assignment_b not in a_assigns

    b_assigns = list(VehicleDriverAssignment.objects.filter(tenant=tenant_b))
    assert driver_assignment_b in b_assigns
    assert driver_assignment_a not in b_assigns

    # VehicleServiceSchedule
    a_services = list(VehicleServiceSchedule.objects.filter(tenant=tenant_a))
    assert service_schedule_a in a_services
    assert service_schedule_b not in a_services

    b_services = list(VehicleServiceSchedule.objects.filter(tenant=tenant_b))
    assert service_schedule_b in b_services
    assert service_schedule_a not in b_services


def test_fleetvehicle_model_unique_constraints(
    tenant_a,
    tenant_b,
    fleet_vehicle_a,
    fuel_log_a,
    driver_assignment_a,
    service_schedule_a,
):
    # 1. FleetVehicle: assets_flt_ten_num_uniq
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FleetVehicle.objects.create(
                tenant=tenant_a,
                number=fleet_vehicle_a.number,
                name="Duplicate Fleet Vehicle",
                license_plate="DUP-01",
                make="Ford",
                model="Transit",
                year=2023,
            )

    # Allowed across tenants with same number
    veh_cross = FleetVehicle.objects.create(
        tenant=tenant_b,
        number=fleet_vehicle_a.number,
        name="Tenant B Matching Number",
        license_plate="MATCH-01",
        make="Ford",
        model="Transit",
        year=2023,
    )
    assert veh_cross.number == fleet_vehicle_a.number

    # 2. VehicleFuelLog: assets_vful_ten_num_uniq
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VehicleFuelLog.objects.create(
                tenant=tenant_a,
                number=fuel_log_a.number,
                vehicle=fleet_vehicle_a,
                odometer_at_fueling=45000,
                quantity_gallons=Decimal("10.000"),
                unit_price=Decimal("4.000"),
            )

    log_cross = VehicleFuelLog.objects.create(
        tenant=tenant_b,
        number=fuel_log_a.number,
        vehicle=veh_cross,
        odometer_at_fueling=12000,
        quantity_gallons=Decimal("10.000"),
        unit_price=Decimal("4.000"),
    )
    assert log_cross.number == fuel_log_a.number

    # 3. VehicleDriverAssignment: assets_vdrv_ten_num_uniq
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VehicleDriverAssignment.objects.create(
                tenant=tenant_a,
                number=driver_assignment_a.number,
                vehicle=fleet_vehicle_a,
                driver=driver_assignment_a.driver,
            )

    # 4. VehicleServiceSchedule: assets_vsrv_ten_num_uniq
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VehicleServiceSchedule.objects.create(
                tenant=tenant_a,
                number=service_schedule_a.number,
                vehicle=fleet_vehicle_a,
                service_title="Duplicate Srv",
            )
