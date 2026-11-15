"""
Unit tests for Module 11.19: Fleet & Vehicle Management Forms.
Covers FleetVehicleForm, VehicleFuelLogForm, VehicleDriverAssignmentForm,
VehicleServiceScheduleForm, form validations, FK queryset tenant isolation,
cross-tenant rejection (reject_foreign), system/telemetry field exclusions,
and instance updates.
"""

from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms import (
    FleetVehicleForm,
    VehicleDriverAssignmentForm,
    VehicleFuelLogForm,
    VehicleServiceScheduleForm,
    reject_foreign,
)
from apps.assets.forms.FleetVehicleManagement import (
    FleetVehicleForm as DirectFleetVehicleForm,
    VehicleDriverAssignmentForm as DirectVehicleDriverAssignmentForm,
    VehicleFuelLogForm as DirectVehicleFuelLogForm,
    VehicleServiceScheduleForm as DirectVehicleServiceScheduleForm,
)
from apps.assets.models import (
    AssetCategory,
    AssetMaintenanceSchedule,
    AssetModel,
    AssetWarranty,
    FleetVehicle,
    VehicleDriverAssignment,
    VehicleFuelLog,
    VehicleServiceSchedule,
)
from apps.core.models import OrgUnit, Party
from apps.hrm.models import EmployeeProfile
from apps.scm.models import Asset

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (Must start with _fleetvehicle_*)
# =====================================================================


def _fleetvehicle_valid_vehicle_payload(**overrides):
    today = timezone.localdate()
    data = {
        "name": "Cargo Van Fleet 301",
        "vin": "1FTNE3Y89PKB33333",
        "license_plate": "VAN-301",
        "registration_state": "CA",
        "make": "Ford",
        "model": "Transit 250",
        "year": 2024,
        "vehicle_type": "cargo_van",
        "fuel_type": "gasoline",
        "ownership_type": "owned",
        "title_number": "TITLE-301-CA",
        "registration_expiration_date": (today + timedelta(days=365)).isoformat(),
        "safety_inspection_due_date": (today + timedelta(days=180)).isoformat(),
        "emissions_inspection_due_date": (today + timedelta(days=365)).isoformat(),
        "current_odometer": 12500,
        "engine_hours": "320.50",
        "gross_vehicle_weight_rating_lbs": 9070,
        "fuel_tank_capacity_gallons": "25.00",
        "battery_capacity_kwh": "",
        "is_telematics_enabled": True,
        "telematics_device_id": "TEL-301-GPS",
        "notes": "Primary delivery van.",
    }
    data.update(overrides)
    return data


def _fleetvehicle_valid_fuel_payload(vehicle, **overrides):
    now = timezone.now()
    data = {
        "vehicle": str(vehicle.pk),
        "fuel_date": now.strftime("%Y-%m-%dT%H:%M"),
        "odometer_at_fueling": 43500,
        "fuel_type": "regular_gasoline",
        "quantity_gallons": "22.500",
        "unit_price": "4.200",
        "total_cost": "94.50",
        "is_full_tank": True,
        "fuel_card_token": "CARD-****-5544",
        "fuel_station_name": "Shell Express 102",
        "station_city_state": "San Jose, CA",
        "route_category": "mixed_delivery",
        "receipt_reference": "RCP-SHL-5544",
        "notes": "Route fuel fill.",
    }
    data.update(overrides)
    return data


def _fleetvehicle_valid_assignment_payload(vehicle, driver, user=None, **overrides):
    now = timezone.now()
    today = timezone.localdate()
    data = {
        "vehicle": str(vehicle.pk),
        "driver": str(driver.pk),
        "assignment_role": "primary_assigned",
        "start_datetime": (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        "end_datetime": (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
        "start_odometer": 42000,
        "end_odometer": 42600,
        "driver_license_number": "DL-998877",
        "driver_license_state": "CA",
        "license_class": "standard_non_cdl",
        "license_expiration_date": (today + timedelta(days=400)).isoformat(),
        "medical_card_expiration_date": (today + timedelta(days=300)).isoformat(),
        "hazmat_endorsed": False,
        "duty_status": "driving",
        "supervisor_notes": "Weekly route driver dispatch.",
    }
    if user is not None:
        data["user"] = str(user.pk)
    data.update(overrides)
    return data


def _fleetvehicle_valid_service_payload(vehicle, vendor=None, currency=None, **overrides):
    today = timezone.localdate()
    data = {
        "vehicle": str(vehicle.pk),
        "service_title": "30,000 Mile Scheduled Service",
        "service_type": "engine_oil_filter",
        "interval_mileage": 5000,
        "interval_months": 6,
        "last_service_date": (today - timedelta(days=45)).isoformat(),
        "last_service_odometer": 25000,
        "next_due_date": (today + timedelta(days=135)).isoformat(),
        "next_due_odometer": 30000,
        "priority": "scheduled_pm",
        "estimated_cost": "220.00",
        "is_warranty_covered": False,
        "work_order_invoice_ref": "INV-SVC-30000",
        "technician_resolution_notes": "Lube, oil, filter and 21-point safety inspection.",
    }
    if vendor is not None:
        data["service_vendor"] = str(vendor.pk)
    if currency is not None:
        data["currency"] = str(currency.pk)
    data.update(overrides)
    return data


# =====================================================================
# 1. FleetVehicleForm Tests
# =====================================================================


def test_fleetvehicle_form_vehicle_valid_save(tenant_a, org_unit_a, driver_profile_a, vendor_party_a):
    """Valid payload saves successfully, sets tenant and generates FLT- number."""
    payload = _fleetvehicle_valid_vehicle_payload(
        org_unit=str(org_unit_a.pk),
        primary_driver=str(driver_profile_a.pk),
        custodian_party=str(vendor_party_a.pk),
    )
    form = FleetVehicleForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    vehicle = form.save()
    assert vehicle.pk is not None
    assert vehicle.tenant == tenant_a
    assert vehicle.number.startswith("FLT-")
    assert vehicle.name == "Cargo Van Fleet 301"
    assert vehicle.make == "Ford"
    assert vehicle.model == "Transit 250"
    assert vehicle.year == 2024
    assert vehicle.org_unit == org_unit_a
    assert vehicle.primary_driver == driver_profile_a
    assert vehicle.custodian_party == vendor_party_a
    assert vehicle.status == "staged_available"
    assert vehicle.compliance_status == "compliant"


def test_fleetvehicle_form_vehicle_required_fields(tenant_a):
    """Missing or empty required fields raise validation errors."""
    form = FleetVehicleForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "license_plate" in form.errors
    assert "make" in form.errors
    assert "model" in form.errors
    assert "year" in form.errors

    # Empty choices for choice fields
    form_empty_choices = FleetVehicleForm(
        data=_fleetvehicle_valid_vehicle_payload(
            vehicle_type="",
            fuel_type="",
            ownership_type="",
        ),
        tenant=tenant_a,
    )
    assert not form_empty_choices.is_valid()
    assert "vehicle_type" in form_empty_choices.errors
    assert "fuel_type" in form_empty_choices.errors
    assert "ownership_type" in form_empty_choices.errors


def test_fleetvehicle_form_vehicle_year_validation(tenant_a):
    """Year must be between 1900 and current_year + 2."""
    current_year = timezone.now().year

    # Below 1900 rejected
    form_low = FleetVehicleForm(
        data=_fleetvehicle_valid_vehicle_payload(year=1899),
        tenant=tenant_a,
    )
    assert not form_low.is_valid()
    assert "year" in form_low.errors

    # Beyond current_year + 2 rejected
    form_high = FleetVehicleForm(
        data=_fleetvehicle_valid_vehicle_payload(year=current_year + 3),
        tenant=tenant_a,
    )
    assert not form_high.is_valid()
    assert "year" in form_high.errors

    # Beyond 2100 rejected
    form_extreme = FleetVehicleForm(
        data=_fleetvehicle_valid_vehicle_payload(year=2105),
        tenant=tenant_a,
    )
    assert not form_extreme.is_valid()
    assert "year" in form_extreme.errors

    # Boundaries 1900 and current_year + 2 are valid
    form_1900 = FleetVehicleForm(
        data=_fleetvehicle_valid_vehicle_payload(year=1900),
        tenant=tenant_a,
    )
    assert form_1900.is_valid(), form_1900.errors

    form_max = FleetVehicleForm(
        data=_fleetvehicle_valid_vehicle_payload(year=current_year + 2),
        tenant=tenant_a,
    )
    assert form_max.is_valid(), form_max.errors


def test_fleetvehicle_form_vehicle_fk_scoping(
    tenant_a,
    tenant_b,
    org_unit_a,
    org_unit_b,
    driver_profile_a,
    driver_profile_b,
    vendor_party_a,
    vendor_party_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    category_a,
    category_b,
    asset_model_a,
    asset_model_b,
):
    """FK field querysets are strictly scoped to the tenant workspace."""
    form_a = FleetVehicleForm(tenant=tenant_a)
    assert org_unit_a in form_a.fields["org_unit"].queryset
    assert org_unit_b not in form_a.fields["org_unit"].queryset

    assert driver_profile_a in form_a.fields["primary_driver"].queryset
    assert driver_profile_b not in form_a.fields["primary_driver"].queryset

    assert vendor_party_a in form_a.fields["custodian_party"].queryset
    assert vendor_party_b not in form_a.fields["custodian_party"].queryset

    assert operational_asset_a in form_a.fields["operational_asset"].queryset
    assert operational_asset_b not in form_a.fields["operational_asset"].queryset

    assert fixed_asset_a in form_a.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form_a.fields["fixed_asset"].queryset

    assert category_a in form_a.fields["asset_category"].queryset
    assert category_b not in form_a.fields["asset_category"].queryset

    assert asset_model_a in form_a.fields["asset_model"].queryset
    assert asset_model_b not in form_a.fields["asset_model"].queryset

    # Form with tenant_b inverts the membership
    form_b = FleetVehicleForm(tenant=tenant_b)
    assert org_unit_b in form_b.fields["org_unit"].queryset
    assert org_unit_a not in form_b.fields["org_unit"].queryset


def test_fleetvehicle_form_vehicle_cross_tenant_rejection(
    tenant_a,
    tenant_b,
    org_unit_b,
    driver_profile_b,
    vendor_party_b,
    operational_asset_b,
    fixed_asset_b,
    category_b,
    asset_model_b,
):
    """Passing foreign tenant FKs triggers reject_foreign validation errors."""
    foreign_cases = [
        ("org_unit", org_unit_b.pk),
        ("primary_driver", driver_profile_b.pk),
        ("custodian_party", vendor_party_b.pk),
        ("operational_asset", operational_asset_b.pk),
        ("fixed_asset", fixed_asset_b.pk),
        ("asset_category", category_b.pk),
        ("asset_model", asset_model_b.pk),
    ]

    for field_name, foreign_pk in foreign_cases:
        payload = _fleetvehicle_valid_vehicle_payload(**{field_name: str(foreign_pk)})
        form = FleetVehicleForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors
        assert any(
            "That record belongs to another workspace." in err
            or "Select a valid choice" in err
            for err in form.errors[field_name]
        )


def test_fleetvehicle_form_vehicle_system_fields_excluded(tenant_a):
    """System fields, telemetry state, and workflow statuses are excluded from form Meta."""
    forbidden = [
        "tenant",
        "number",
        "is_locked",
        "created_at",
        "updated_at",
        "engine_state",
        "geofence_status",
        "status",
        "compliance_status",
        "current_latitude",
        "current_longitude",
        "current_speed_mph",
        "current_heading",
        "last_telemetry_at",
    ]
    meta_fields = set(FleetVehicleForm.Meta.fields)
    form = FleetVehicleForm(tenant=tenant_a)
    for field in forbidden:
        assert field not in meta_fields, f"Leaked {field} in Meta.fields"
        assert field not in form.fields, f"Leaked {field} in form.fields"


def test_fleetvehicle_form_vehicle_update_instance(tenant_a, fleet_vehicle_a, org_unit_a):
    """Bound instance updates save properly without tenant drift."""
    payload = _fleetvehicle_valid_vehicle_payload(
        name="Updated Ford Transit Fleet 101",
        license_plate="VAN-101-UPD",
        current_odometer=45000,
        org_unit=str(org_unit_a.pk),
    )
    form = FleetVehicleForm(instance=fleet_vehicle_a, data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == fleet_vehicle_a.pk
    assert updated.name == "Updated Ford Transit Fleet 101"
    assert updated.license_plate == "VAN-101-UPD"
    assert updated.current_odometer == 45000
    assert updated.tenant == tenant_a


# =====================================================================
# 2. VehicleFuelLogForm Tests
# =====================================================================


def test_fleetvehicle_form_fuel_log_valid_save_and_calculations(
    tenant_a,
    fleet_vehicle_a,
    driver_profile_a,
    vendor_party_a,
    currency_usd,
):
    """Valid fuel log payload saves correctly with total_cost calculations."""
    payload = _fleetvehicle_valid_fuel_payload(
        fleet_vehicle_a,
        driver=str(driver_profile_a.pk),
        fuel_vendor=str(vendor_party_a.pk),
        currency=str(currency_usd.pk),
        quantity_gallons="20.000",
        unit_price="4.500",
        total_cost="90.00",
    )
    form = VehicleFuelLogForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    log = form.save()
    assert log.pk is not None
    assert log.tenant == tenant_a
    assert log.vehicle == fleet_vehicle_a
    assert log.driver == driver_profile_a
    assert log.fuel_vendor == vendor_party_a
    assert log.currency == currency_usd
    assert log.quantity_gallons == Decimal("20.000")
    assert log.total_cost == Decimal("90.00")
    assert log.number.startswith("VFUL-")


def test_fleetvehicle_form_fuel_log_negative_zero_quantity_rejected(tenant_a, fleet_vehicle_a):
    """Quantity gallons <= 0 is rejected with a validation error."""
    # Zero quantity
    form_zero = VehicleFuelLogForm(
        data=_fleetvehicle_valid_fuel_payload(fleet_vehicle_a, quantity_gallons="0.000"),
        tenant=tenant_a,
    )
    assert not form_zero.is_valid()
    assert "quantity_gallons" in form_zero.errors
    assert "Quantity pumped must be greater than zero." in form_zero.errors["quantity_gallons"]

    # Negative quantity
    form_neg = VehicleFuelLogForm(
        data=_fleetvehicle_valid_fuel_payload(fleet_vehicle_a, quantity_gallons="-15.500"),
        tenant=tenant_a,
    )
    assert not form_neg.is_valid()
    assert "quantity_gallons" in form_neg.errors


def test_fleetvehicle_form_fuel_log_negative_odometer_rejected(tenant_a, fleet_vehicle_a):
    """Negative odometer at fueling is rejected."""
    form_neg_odo = VehicleFuelLogForm(
        data=_fleetvehicle_valid_fuel_payload(fleet_vehicle_a, odometer_at_fueling=-50),
        tenant=tenant_a,
    )
    assert not form_neg_odo.is_valid()
    assert "odometer_at_fueling" in form_neg_odo.errors
    assert any(
        "greater than or equal to 0" in err or "cannot be negative" in err
        for err in form_neg_odo.errors["odometer_at_fueling"]
    )


def test_fleetvehicle_form_fuel_log_fk_scoping(
    tenant_a,
    tenant_b,
    fleet_vehicle_a,
    fleet_vehicle_b,
    driver_profile_a,
    driver_profile_b,
    vendor_party_a,
    vendor_party_b,
):
    """Vehicle, driver, and vendor querysets are filtered by tenant."""
    form = VehicleFuelLogForm(tenant=tenant_a)
    assert fleet_vehicle_a in form.fields["vehicle"].queryset
    assert fleet_vehicle_b not in form.fields["vehicle"].queryset

    assert driver_profile_a in form.fields["driver"].queryset
    assert driver_profile_b not in form.fields["driver"].queryset

    assert vendor_party_a in form.fields["fuel_vendor"].queryset
    assert vendor_party_b not in form.fields["fuel_vendor"].queryset


def test_fleetvehicle_form_fuel_log_cross_tenant_rejection(
    tenant_a,
    fleet_vehicle_a,
    fleet_vehicle_b,
    driver_profile_b,
    vendor_party_b,
):
    """Cross-tenant FK references are blocked by reject_foreign."""
    # Cross-tenant vehicle
    bad_veh = VehicleFuelLogForm(
        data=_fleetvehicle_valid_fuel_payload(fleet_vehicle_b),
        tenant=tenant_a,
    )
    assert not bad_veh.is_valid()
    assert "vehicle" in bad_veh.errors

    # Cross-tenant driver
    bad_driver = VehicleFuelLogForm(
        data=_fleetvehicle_valid_fuel_payload(fleet_vehicle_a, driver=str(driver_profile_b.pk)),
        tenant=tenant_a,
    )
    assert not bad_driver.is_valid()
    assert "driver" in bad_driver.errors

    # Cross-tenant vendor
    bad_vendor = VehicleFuelLogForm(
        data=_fleetvehicle_valid_fuel_payload(fleet_vehicle_a, fuel_vendor=str(vendor_party_b.pk)),
        tenant=tenant_a,
    )
    assert not bad_vendor.is_valid()
    assert "fuel_vendor" in bad_vendor.errors


def test_fleetvehicle_form_fuel_log_decommissioned_vehicle_handling(tenant_a, fleet_vehicle_a):
    """Decommissioned vehicles are excluded from vehicle queryset unless already bound."""
    retired = FleetVehicle.objects.create(
        tenant=tenant_a,
        name="Retired Ford E-350",
        license_plate="RET-350",
        make="Ford",
        model="E-350",
        year=2012,
        status="decommissioned",
    )

    # New form excludes decommissioned vehicle
    form_new = VehicleFuelLogForm(tenant=tenant_a)
    assert retired not in form_new.fields["vehicle"].queryset
    assert fleet_vehicle_a in form_new.fields["vehicle"].queryset

    # Editing existing log bound to decommissioned vehicle retains it
    existing_log = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=retired,
        odometer_at_fueling=150000,
        quantity_gallons=Decimal("30.000"),
        unit_price=Decimal("4.000"),
        total_cost=Decimal("120.00"),
    )
    form_edit = VehicleFuelLogForm(instance=existing_log, tenant=tenant_a)
    assert retired in form_edit.fields["vehicle"].queryset


def test_fleetvehicle_form_fuel_log_currency_active_filtering(tenant_a, currency_usd):
    """Global currency choices exclude inactive currencies."""
    inactive_curr, _ = Currency.objects.get_or_create(
        code="XIN",
        defaults={"name": "Inactive Currency", "symbol": "X", "is_active": False},
    )
    form = VehicleFuelLogForm(tenant=tenant_a)
    assert currency_usd in form.fields["currency"].queryset
    assert inactive_curr not in form.fields["currency"].queryset


def test_fleetvehicle_form_fuel_log_update_instance(tenant_a, fuel_log_a, fleet_vehicle_a):
    """Editing an existing fuel log instance updates properly."""
    payload = _fleetvehicle_valid_fuel_payload(
        fleet_vehicle_a,
        notes="Updated pump receipt reference note.",
        receipt_reference="RCP-UPD-9999",
        total_cost="99.00",
    )
    form = VehicleFuelLogForm(instance=fuel_log_a, data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == fuel_log_a.pk
    assert updated.notes == "Updated pump receipt reference note."
    assert updated.receipt_reference == "RCP-UPD-9999"
    assert updated.total_cost == Decimal("99.00")
    assert updated.tenant == tenant_a


# =====================================================================
# 3. VehicleDriverAssignmentForm Tests
# =====================================================================


def test_fleetvehicle_form_driver_assignment_valid_save(
    tenant_a,
    fleet_vehicle_a,
    driver_profile_a,
    user_a,
):
    """Valid assignment payload saves properly and links user account."""
    payload = _fleetvehicle_valid_assignment_payload(
        fleet_vehicle_a,
        driver_profile_a,
        user=user_a,
    )
    form = VehicleDriverAssignmentForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    assign = form.save()
    assert assign.pk is not None
    assert assign.tenant == tenant_a
    assert assign.vehicle == fleet_vehicle_a
    assert assign.driver == driver_profile_a
    assert assign.user == user_a
    assert assign.assignment_role == "primary_assigned"
    assert assign.number.startswith("VDRV-")
    assert assign.status == "active"


def test_fleetvehicle_form_driver_assignment_end_datetime_precedes_start(
    tenant_a,
    fleet_vehicle_a,
    driver_profile_a,
):
    """End datetime before start datetime raises form validation error."""
    now = timezone.now()
    payload = _fleetvehicle_valid_assignment_payload(
        fleet_vehicle_a,
        driver_profile_a,
        start_datetime=(now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        end_datetime=(now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
    )
    form = VehicleDriverAssignmentForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_datetime" in form.errors
    assert "End datetime cannot precede start datetime." in form.errors["end_datetime"]


def test_fleetvehicle_form_driver_assignment_end_odometer_less_than_start(
    tenant_a,
    fleet_vehicle_a,
    driver_profile_a,
):
    """Ending odometer reading less than starting odometer raises error."""
    payload = _fleetvehicle_valid_assignment_payload(
        fleet_vehicle_a,
        driver_profile_a,
        start_odometer=50000,
        end_odometer=48000,
    )
    form = VehicleDriverAssignmentForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_odometer" in form.errors
    assert "Ending odometer cannot be less than starting odometer." in form.errors["end_odometer"]


def test_fleetvehicle_form_driver_assignment_fk_scoping(
    tenant_a,
    tenant_b,
    fleet_vehicle_a,
    fleet_vehicle_b,
    driver_profile_a,
    driver_profile_b,
    user_a,
    user_b,
):
    """Vehicle, driver profile, and user accounts are scoped to tenant."""
    form = VehicleDriverAssignmentForm(tenant=tenant_a)
    assert fleet_vehicle_a in form.fields["vehicle"].queryset
    assert fleet_vehicle_b not in form.fields["vehicle"].queryset

    assert driver_profile_a in form.fields["driver"].queryset
    assert driver_profile_b not in form.fields["driver"].queryset

    assert user_a in form.fields["user"].queryset
    assert user_b not in form.fields["user"].queryset


def test_fleetvehicle_form_driver_assignment_cross_tenant_rejection(
    tenant_a,
    fleet_vehicle_a,
    fleet_vehicle_b,
    driver_profile_a,
    driver_profile_b,
    user_b,
):
    """Cross-tenant FK submissions are caught by reject_foreign."""
    # Cross-tenant vehicle
    bad_v = VehicleDriverAssignmentForm(
        data=_fleetvehicle_valid_assignment_payload(fleet_vehicle_b, driver_profile_a),
        tenant=tenant_a,
    )
    assert not bad_v.is_valid()
    assert "vehicle" in bad_v.errors

    # Cross-tenant driver
    bad_d = VehicleDriverAssignmentForm(
        data=_fleetvehicle_valid_assignment_payload(fleet_vehicle_a, driver_profile_b),
        tenant=tenant_a,
    )
    assert not bad_d.is_valid()
    assert "driver" in bad_d.errors

    # Cross-tenant user
    bad_u = VehicleDriverAssignmentForm(
        data=_fleetvehicle_valid_assignment_payload(fleet_vehicle_a, driver_profile_a, user=user_b),
        tenant=tenant_a,
    )
    assert not bad_u.is_valid()
    assert "user" in bad_u.errors


def test_fleetvehicle_form_driver_assignment_telemetry_fields_excluded(tenant_a):
    """Telemetry counters and system fields are excluded from mass-assignment."""
    excluded = [
        "speeding_event_count",
        "harsh_braking_count",
        "harsh_acceleration_count",
        "incident_count",
        "safety_score",
        "safety_tier",
        "qualification_status",
        "status",
        "tenant",
        "number",
        "is_locked",
        "created_at",
        "updated_at",
    ]
    meta_fields = set(VehicleDriverAssignmentForm.Meta.fields)
    form = VehicleDriverAssignmentForm(tenant=tenant_a)
    for field in excluded:
        assert field not in meta_fields, f"Leaked {field} in Meta.fields"
        assert field not in form.fields, f"Leaked {field} in form.fields"


def test_fleetvehicle_form_driver_assignment_update_instance(
    tenant_a,
    driver_assignment_a,
    fleet_vehicle_a,
    driver_profile_a,
):
    """Updating driver assignment preserves instance identity and tenant."""
    payload = _fleetvehicle_valid_assignment_payload(
        fleet_vehicle_a,
        driver_profile_a,
        supervisor_notes="Updated safety coaching notes.",
        duty_status="on_duty_not_driving",
    )
    form = VehicleDriverAssignmentForm(instance=driver_assignment_a, data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == driver_assignment_a.pk
    assert updated.supervisor_notes == "Updated safety coaching notes."
    assert updated.duty_status == "on_duty_not_driving"
    assert updated.tenant == tenant_a


# =====================================================================
# 4. VehicleServiceScheduleForm Tests
# =====================================================================


def test_fleetvehicle_form_service_schedule_valid_save(
    tenant_a,
    fleet_vehicle_a,
    vendor_party_a,
    currency_usd,
):
    """Valid service schedule payload saves properly."""
    payload = _fleetvehicle_valid_service_payload(
        fleet_vehicle_a,
        vendor=vendor_party_a,
        currency=currency_usd,
        service_title="Comprehensive 60k Mile Inspection",
        priority="high_priority",
        estimated_cost="350.00",
    )
    form = VehicleServiceScheduleForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    srv = form.save()
    assert srv.pk is not None
    assert srv.tenant == tenant_a
    assert srv.vehicle == fleet_vehicle_a
    assert srv.service_vendor == vendor_party_a
    assert srv.currency == currency_usd
    assert srv.service_title == "Comprehensive 60k Mile Inspection"
    assert srv.priority == "high_priority"
    assert srv.estimated_cost == Decimal("350.00")
    assert srv.number.startswith("VSRV-")
    assert srv.status == "active_tracking"


def test_fleetvehicle_form_service_schedule_negative_interval_rejected(
    tenant_a,
    fleet_vehicle_a,
):
    """Negative interval mileage or interval months are rejected."""
    # Negative mileage interval
    form_neg_m = VehicleServiceScheduleForm(
        data=_fleetvehicle_valid_service_payload(fleet_vehicle_a, interval_mileage=-1000),
        tenant=tenant_a,
    )
    assert not form_neg_m.is_valid()
    assert "interval_mileage" in form_neg_m.errors
    assert any(
        "greater than or equal to 0" in err or "cannot be negative" in err
        for err in form_neg_m.errors["interval_mileage"]
    )

    # Negative months interval
    form_neg_mo = VehicleServiceScheduleForm(
        data=_fleetvehicle_valid_service_payload(fleet_vehicle_a, interval_months=-3),
        tenant=tenant_a,
    )
    assert not form_neg_mo.is_valid()
    assert "interval_months" in form_neg_mo.errors
    assert any(
        "greater than or equal to 0" in err or "cannot be negative" in err
        for err in form_neg_mo.errors["interval_months"]
    )


def test_fleetvehicle_form_service_schedule_fk_scoping(
    tenant_a,
    tenant_b,
    fleet_vehicle_a,
    fleet_vehicle_b,
    vendor_party_a,
    vendor_party_b,
    currency_usd,
    maintenance_schedule_a,
    maintenance_schedule_b,
    warranty_a,
    warranty_b,
):
    """Vehicle, vendor, warranty, and maintenance schedule are scoped to tenant."""
    form = VehicleServiceScheduleForm(tenant=tenant_a)
    assert fleet_vehicle_a in form.fields["vehicle"].queryset
    assert fleet_vehicle_b not in form.fields["vehicle"].queryset

    assert vendor_party_a in form.fields["service_vendor"].queryset
    assert vendor_party_b not in form.fields["service_vendor"].queryset

    assert warranty_a in form.fields["warranty"].queryset
    assert warranty_b not in form.fields["warranty"].queryset

    assert maintenance_schedule_a in form.fields["maintenance_schedule"].queryset
    assert maintenance_schedule_b not in form.fields["maintenance_schedule"].queryset

    assert currency_usd in form.fields["currency"].queryset


def test_fleetvehicle_form_service_schedule_cross_tenant_rejection(
    tenant_a,
    fleet_vehicle_a,
    fleet_vehicle_b,
    vendor_party_b,
    warranty_b,
    maintenance_schedule_b,
):
    """Cross-tenant references fail form clean."""
    # Cross-tenant vehicle
    bad_v = VehicleServiceScheduleForm(
        data=_fleetvehicle_valid_service_payload(fleet_vehicle_b),
        tenant=tenant_a,
    )
    assert not bad_v.is_valid()
    assert "vehicle" in bad_v.errors

    # Cross-tenant vendor
    bad_vendor = VehicleServiceScheduleForm(
        data=_fleetvehicle_valid_service_payload(fleet_vehicle_a, service_vendor=str(vendor_party_b.pk)),
        tenant=tenant_a,
    )
    assert not bad_vendor.is_valid()
    assert "service_vendor" in bad_vendor.errors

    # Cross-tenant warranty
    bad_w = VehicleServiceScheduleForm(
        data=_fleetvehicle_valid_service_payload(fleet_vehicle_a, warranty=str(warranty_b.pk)),
        tenant=tenant_a,
    )
    assert not bad_w.is_valid()
    assert "warranty" in bad_w.errors

    # Cross-tenant maintenance schedule
    bad_ms = VehicleServiceScheduleForm(
        data=_fleetvehicle_valid_service_payload(fleet_vehicle_a, maintenance_schedule=str(maintenance_schedule_b.pk)),
        tenant=tenant_a,
    )
    assert not bad_ms.is_valid()
    assert "maintenance_schedule" in bad_ms.errors


def test_fleetvehicle_form_service_schedule_system_fields_excluded(tenant_a):
    """Workflow status and system fields are excluded from Meta."""
    forbidden = [
        "tenant",
        "number",
        "is_locked",
        "created_at",
        "updated_at",
        "status",
        "actual_cost",
    ]
    meta_fields = set(VehicleServiceScheduleForm.Meta.fields)
    form = VehicleServiceScheduleForm(tenant=tenant_a)
    for field in forbidden:
        assert field not in meta_fields, f"Leaked {field} in Meta.fields"
        assert field not in form.fields, f"Leaked {field} in form.fields"


def test_fleetvehicle_form_service_schedule_update_instance(
    tenant_a,
    service_schedule_a,
    fleet_vehicle_a,
):
    """Editing service schedule preserves PK and tenant."""
    payload = _fleetvehicle_valid_service_payload(
        fleet_vehicle_a,
        service_title="Updated 45k Mile PM Service",
        estimated_cost="240.00",
        technician_resolution_notes="Updated technician recommendations.",
    )
    form = VehicleServiceScheduleForm(instance=service_schedule_a, data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == service_schedule_a.pk
    assert updated.service_title == "Updated 45k Mile PM Service"
    assert updated.estimated_cost == Decimal("240.00")
    assert updated.technician_resolution_notes == "Updated technician recommendations."
    assert updated.tenant == tenant_a


# =====================================================================
# 5. Re-exports & Direct Imports
# =====================================================================


def test_fleetvehicle_form_reexports_and_imports():
    """Verify that form classes match across direct and package-level imports."""
    assert FleetVehicleForm is DirectFleetVehicleForm
    assert VehicleFuelLogForm is DirectVehicleFuelLogForm
    assert VehicleDriverAssignmentForm is DirectVehicleDriverAssignmentForm
    assert VehicleServiceScheduleForm is DirectVehicleServiceScheduleForm
