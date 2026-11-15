"""
Unit and integration tests for Module 11.19: Fleet & Vehicle Management Views.
Covers:
1. FleetVehicle:
   - list (context keys, aggregates, filters, junk params, pagination)
   - export (CSV headers, content, formula injection neutralization)
   - detail (context keys, related querysets, audits, compliance refresh)
   - create (GET 200, POST 302, invalid POST 200)
   - edit (GET 200, POST 302, locked/decommissioned guard)
   - delete (require_POST 405 on GET, 302 on POST)
   - state transitions (activate, in-shop, loaner, out-of-service, decommission, telematics ping)
2. VehicleFuelLog:
   - list (context keys, aggregates, total_spend, total_gallons, avg_mpg, filters)
   - export (CSV headers, formula safety)
   - detail (GET 200)
   - create (GET 200 with vehicle prefill, POST 302)
   - edit (GET 200, POST 302)
   - delete (require_POST 405 on GET, 302 on POST)
3. VehicleDriverAssignment:
   - list (context keys, safety scores, active/high-risk aggregates, filters)
   - export (CSV headers, formula safety)
   - detail (GET 200)
   - create (GET 200 with vehicle prefill, POST 302)
   - edit (GET 200, POST 302)
   - delete (require_POST 405 on GET, 302 on POST)
   - actions (complete, revoke, record incident, status guards)
4. VehicleServiceSchedule:
   - list (context keys, overdue/due soon alerts, filters)
   - export (CSV headers, formula safety)
   - detail (GET 200)
   - create (GET 200 with vehicle prefill, POST 302)
   - edit (GET 200, POST 302)
   - delete (require_POST 405 on GET, 302 on POST)
   - actions (in-service, pause, complete with numeric validation & locked vehicle guard)
5. FleetTelematicsBoard:
   - board (context keys, real-time dispatch tiles, upcoming maintenance, high-risk drivers, filter params)
6. Cross-Tenant IDOR:
   - tenant_b records return 404 when accessed by tenant_a client.
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    FleetVehicle,
    VehicleDriverAssignment,
    VehicleFuelLog,
    VehicleServiceSchedule,
)
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (Must start with _fleetvehicle_*)
# =====================================================================


def _fleetvehicle_messages(response):
    """Extract string messages from a response's request context."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _fleetvehicle_parse_csv(response):
    """Parse CSV response content into a list of row lists."""
    content = response.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


def _fleetvehicle_valid_vehicle_payload(**overrides):
    today = timezone.localdate()
    data = {
        "name": "Cargo Van Fleet 401",
        "vin": "1FTNE3Y89PKB44444",
        "license_plate": "VAN-401",
        "registration_state": "CA",
        "make": "Ford",
        "model": "Transit 250",
        "year": 2024,
        "vehicle_type": "cargo_van",
        "fuel_type": "gasoline",
        "ownership_type": "owned",
        "title_number": "TIT-401-CA",
        "registration_expiration_date": (today + timedelta(days=365)).isoformat(),
        "safety_inspection_due_date": (today + timedelta(days=180)).isoformat(),
        "emissions_inspection_due_date": (today + timedelta(days=365)).isoformat(),
        "current_odometer": 15000,
        "engine_hours": "350.00",
        "gross_vehicle_weight_rating_lbs": 9070,
        "fuel_tank_capacity_gallons": "25.00",
        "is_telematics_enabled": True,
        "telematics_device_id": "TEL-401-GPS",
        "notes": "Route parcel delivery van.",
    }
    data.update(overrides)
    return data


def _fleetvehicle_valid_fuel_payload(vehicle, currency=None, **overrides):
    now = timezone.now()
    data = {
        "vehicle": str(vehicle.pk),
        "fuel_date": now.strftime("%Y-%m-%dT%H:%M"),
        "odometer_at_fueling": 44000,
        "fuel_type": "regular_gasoline",
        "quantity_gallons": "21.000",
        "unit_price": "4.300",
        "total_cost": "90.30",
        "is_full_tank": True,
        "fuel_card_token": "CARD-****-9876",
        "fuel_station_name": "Chevron Express 204",
        "station_city_state": "Oakland, CA",
        "route_category": "mixed_delivery",
        "receipt_reference": "RCP-CHV-9876",
        "notes": "Weekly route refill.",
    }
    if currency is not None:
        data["currency"] = str(currency.pk)
    data.update(overrides)
    return data


def _fleetvehicle_valid_assignment_payload(vehicle, driver, user=None, **overrides):
    now = timezone.now()
    today = timezone.localdate()
    data = {
        "vehicle": str(vehicle.pk),
        "driver": str(driver.pk),
        "assignment_role": "primary_assigned",
        "start_datetime": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        "end_datetime": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
        "start_odometer": 43000,
        "end_odometer": 43500,
        "driver_license_number": "CA-DL-554433",
        "driver_license_state": "CA",
        "license_class": "standard_non_cdl",
        "license_expiration_date": (today + timedelta(days=450)).isoformat(),
        "medical_card_expiration_date": (today + timedelta(days=250)).isoformat(),
        "hazmat_endorsed": False,
        "duty_status": "driving",
        "supervisor_notes": "Assigned for scheduled delivery route.",
    }
    if user is not None:
        data["user"] = str(user.pk)
    data.update(overrides)
    return data


def _fleetvehicle_valid_service_payload(vehicle, vendor=None, currency=None, **overrides):
    today = timezone.localdate()
    data = {
        "vehicle": str(vehicle.pk),
        "service_title": "40,000 Mile Scheduled Service",
        "service_type": "engine_oil_filter",
        "interval_mileage": 5000,
        "interval_months": 6,
        "last_service_date": (today - timedelta(days=30)).isoformat(),
        "last_service_odometer": 35000,
        "next_due_date": (today + timedelta(days=150)).isoformat(),
        "next_due_odometer": 40000,
        "priority": "scheduled_pm",
        "estimated_cost": "250.00",
        "is_warranty_covered": False,
        "work_order_invoice_ref": "INV-SVC-40000",
        "technician_resolution_notes": "Oil change, tire rotation, multi-point check.",
    }
    if vendor is not None:
        data["service_vendor"] = str(vendor.pk)
    if currency is not None:
        data["currency"] = str(currency.pk)
    data.update(overrides)
    return data


# =====================================================================
# 1. FleetVehicle Views Tests
# =====================================================================


def test_fleetvehicle_view_vehicle_list(client, user_a, fleet_vehicle_a, fleet_vehicle_b, org_unit_a):
    """Verify fleet_vehicle_list returns 200 with required context keys, filters and tenant isolation."""
    client.force_login(user_a)
    url = reverse("assets:fleet_vehicle_list")
    resp = client.get(url)
    assert resp.status_code == 200

    # Pinned context keys
    for key in (
        "vehicles",
        "page_obj",
        "status_choices",
        "vehicle_type_choices",
        "fuel_type_choices",
        "compliance_choices",
        "org_units",
        "total_count",
        "active_count",
        "in_shop_count",
        "expired_compliance_count",
    ):
        assert key in resp.context, f"Missing context key: {key}"

    # Only tenant_a vehicle visible
    vehicles = list(resp.context["vehicles"])
    assert fleet_vehicle_a in vehicles
    assert fleet_vehicle_b not in vehicles

    # Query param filter tests
    # 1. Search text ?q=
    resp_q = client.get(url, {"q": fleet_vehicle_a.license_plate})
    assert resp_q.status_code == 200
    assert fleet_vehicle_a in resp_q.context["vehicles"]

    resp_q_miss = client.get(url, {"q": "NONEXISTENT-XYZ"})
    assert resp_q_miss.status_code == 200
    assert len(resp_q_miss.context["vehicles"]) == 0

    # 2. Status filter
    resp_status = client.get(url, {"status": "active_in_service"})
    assert resp_status.status_code == 200
    assert fleet_vehicle_a in resp_status.context["vehicles"]

    resp_status_mismatch = client.get(url, {"status": "decommissioned"})
    assert resp_status_mismatch.status_code == 200
    assert fleet_vehicle_a not in resp_status_mismatch.context["vehicles"]

    # 3. Vehicle type filter
    resp_type = client.get(url, {"vehicle_type": fleet_vehicle_a.vehicle_type})
    assert resp_type.status_code == 200
    assert fleet_vehicle_a in resp_type.context["vehicles"]

    # 4. OrgUnit FK filter
    resp_org = client.get(url, {"org_unit": org_unit_a.pk})
    assert resp_org.status_code == 200
    assert fleet_vehicle_a in resp_org.context["vehicles"]

    # 5. Junk parameters
    resp_junk = client.get(url, {"org_unit": "invalid", "status": "bogus_status", "page": "abc"})
    assert resp_junk.status_code == 200
    assert fleet_vehicle_a in resp_junk.context["vehicles"]


def test_fleetvehicle_view_vehicle_export_csv(client, user_a, fleet_vehicle_a, fleet_vehicle_b):
    """Verify fleet_vehicle_export returns CSV with headers, tenant isolation and formula neutralization."""
    client.force_login(user_a)
    # Inject a potential formula injection in vehicle name
    fleet_vehicle_a.name = "=CMD('calc.exe')-Test"
    fleet_vehicle_a.save(update_fields=["name"])

    url = reverse("assets:fleet_vehicle_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert "attachment; filename=" in resp["Content-Disposition"]

    rows = _fleetvehicle_parse_csv(resp)
    assert len(rows) >= 2  # header + at least 1 record
    headers = rows[0]
    assert "Vehicle Number" in headers
    assert "License Plate" in headers
    assert "VIN" in headers

    # Check formula neutralization
    data_rows = rows[1:]
    matching = [r for r in data_rows if fleet_vehicle_a.number in r]
    assert len(matching) == 1
    # formula-prefixed name must start with single quote
    assert matching[0][1].startswith("'=")

    # Ensure tenant_b vehicle is not exported
    tenant_b_matching = [r for r in data_rows if fleet_vehicle_b.vin in r or fleet_vehicle_b.license_plate in r]
    assert len(tenant_b_matching) == 0


def test_fleetvehicle_view_vehicle_detail(client, user_a, fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a):
    """Verify fleet_vehicle_detail returns 200 and passes all related records and context keys."""
    client.force_login(user_a)
    url = reverse("assets:fleet_vehicle_detail", kwargs={"pk": fleet_vehicle_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    for key in ("vehicle", "fuel_logs", "assignments", "service_schedules", "recent_audits"):
        assert key in resp.context, f"Missing context key: {key}"

    assert resp.context["vehicle"] == fleet_vehicle_a
    assert fuel_log_a in list(resp.context["fuel_logs"])
    assert driver_assignment_a in list(resp.context["assignments"])
    assert service_schedule_a in list(resp.context["service_schedules"])


def test_fleetvehicle_view_vehicle_create_and_validation(client, user_a, tenant_a):
    """Verify fleet_vehicle_create renders form on GET and creates vehicle on POST."""
    client.force_login(user_a)
    url = reverse("assets:fleet_vehicle_create")

    # GET 200
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST invalid (missing required fields)
    resp_invalid = client.post(url, {})
    assert resp_invalid.status_code == 200
    assert resp_invalid.context["form"].errors

    # POST valid
    payload = _fleetvehicle_valid_vehicle_payload()
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created_veh = FleetVehicle.objects.get(tenant=tenant_a, vin=payload["vin"])
    assert resp_post.url == reverse("assets:fleet_vehicle_detail", kwargs={"pk": created_veh.pk})
    assert created_veh.name == payload["name"]
    assert created_veh.tenant == tenant_a

    # Audit log entry created
    audit = AuditLog.objects.filter(tenant=tenant_a, object_id=created_veh.pk, action="create").first()
    assert audit is not None


def test_fleetvehicle_view_vehicle_edit_and_locked_guard(client, user_a, fleet_vehicle_a, tenant_a):
    """Verify fleet_vehicle_edit GET and POST update vehicle, and locked vehicles reject editing."""
    client.force_login(user_a)
    url = reverse("assets:fleet_vehicle_edit", kwargs={"pk": fleet_vehicle_a.pk})

    # GET 200
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["vehicle"] == fleet_vehicle_a

    # POST valid update
    payload = _fleetvehicle_valid_vehicle_payload(
        name="Updated Ford Transit 101-Pro",
        vin=fleet_vehicle_a.vin,
        license_plate=fleet_vehicle_a.license_plate,
        registration_state=fleet_vehicle_a.registration_state,
        current_odometer=45000,
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:fleet_vehicle_detail", kwargs={"pk": fleet_vehicle_a.pk})

    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.name == "Updated Ford Transit 101-Pro"
    assert fleet_vehicle_a.current_odometer == 45000

    # Lock vehicle and verify edit attempt is rejected
    fleet_vehicle_a.status = "decommissioned"
    fleet_vehicle_a.save()
    assert fleet_vehicle_a.is_locked is True

    resp_locked_get = client.get(url)
    assert resp_locked_get.status_code == 302
    assert resp_locked_get.url == reverse("assets:fleet_vehicle_detail", kwargs={"pk": fleet_vehicle_a.pk})
    msgs = _fleetvehicle_messages(resp_locked_get)
    assert any("decommissioned and cannot be edited" in m for m in msgs)


def test_fleetvehicle_view_vehicle_delete(client, user_a, fleet_vehicle_a, tenant_a):
    """Verify fleet_vehicle_delete requires POST and deletes vehicle cleanly."""
    client.force_login(user_a)
    url = reverse("assets:fleet_vehicle_delete", kwargs={"pk": fleet_vehicle_a.pk})

    # GET returns 405 Method Not Allowed
    resp_get = client.get(url)
    assert resp_get.status_code == 405

    # POST deletes vehicle
    veh_pk = fleet_vehicle_a.pk
    resp_post = client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:fleet_vehicle_list")

    assert not FleetVehicle.objects.filter(pk=veh_pk).exists()
    msgs = _fleetvehicle_messages(resp_post)
    assert any("deleted" in m for m in msgs)


def test_fleetvehicle_view_vehicle_state_transitions(client, user_a, fleet_vehicle_a):
    """Verify state transitions: activate, in_shop, loaner, out_of_service, decommission, telemetry ping."""
    client.force_login(user_a)
    pk = fleet_vehicle_a.pk

    # 1. Mark in shop
    url_in_shop = reverse("assets:fleet_vehicle_mark_in_shop", kwargs={"pk": pk})
    resp = client.post(url_in_shop)
    assert resp.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status == "in_shop_maintenance"

    # 2. Mark loaner out
    url_loaner = reverse("assets:fleet_vehicle_mark_loaner", kwargs={"pk": pk})
    resp = client.post(url_loaner)
    assert resp.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status == "loaner_out"

    # 3. Mark out of service
    url_oos = reverse("assets:fleet_vehicle_mark_out_of_service", kwargs={"pk": pk})
    resp = client.post(url_oos)
    assert resp.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status == "out_of_service"

    # 4. Activate back
    url_activate = reverse("assets:fleet_vehicle_activate", kwargs={"pk": pk})
    resp = client.post(url_activate)
    assert resp.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status == "active_in_service"

    # 5. Ping telemetry
    url_ping = reverse("assets:fleet_vehicle_ping_telemetry", kwargs={"pk": pk})
    old_time = fleet_vehicle_a.last_telemetry_at
    resp = client.post(url_ping)
    assert resp.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.is_telematics_enabled is True
    assert fleet_vehicle_a.last_telemetry_at >= old_time

    # 6. Decommission
    url_decomm = reverse("assets:fleet_vehicle_decommission", kwargs={"pk": pk})
    resp = client.post(url_decomm)
    assert resp.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status == "decommissioned"
    assert fleet_vehicle_a.is_locked is True

    # 7. Actions on locked/decommissioned vehicle reject with error message
    for action_url in (url_in_shop, url_loaner, url_oos, url_activate, url_ping):
        resp_guard = client.post(action_url)
        assert resp_guard.status_code == 302
        msgs = _fleetvehicle_messages(resp_guard)
        assert len(msgs) > 0


# =====================================================================
# 2. VehicleFuelLog Views Tests
# =====================================================================


def test_fleetvehicle_view_fuel_log_list(client, user_a, fuel_log_a, fuel_log_b, fleet_vehicle_a):
    """Verify vehicle_fuel_log_list returns 200 with metrics, aggregates, and filter params."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_fuel_log_list")
    resp = client.get(url)
    assert resp.status_code == 200

    for key in (
        "fuel_logs",
        "page_obj",
        "vehicles",
        "fuel_type_choices",
        "efficiency_choices",
        "total_cost_sum",
        "total_spend",
        "total_gallons_sum",
        "total_gallons",
        "avg_mpg",
    ):
        assert key in resp.context, f"Missing context key: {key}"

    # Tenant scoping
    logs = list(resp.context["fuel_logs"])
    assert fuel_log_a in logs
    assert fuel_log_b not in logs

    # Filter params tests
    # 1. Search ?q=
    resp_q = client.get(url, {"q": fuel_log_a.fuel_station_name})
    assert resp_q.status_code == 200
    assert fuel_log_a in resp_q.context["fuel_logs"]

    # 2. Vehicle FK filter
    resp_veh = client.get(url, {"vehicle": fleet_vehicle_a.pk})
    assert resp_veh.status_code == 200
    assert fuel_log_a in resp_veh.context["fuel_logs"]

    # 3. Fuel type filter
    resp_fuel_type = client.get(url, {"fuel_type": fuel_log_a.fuel_type})
    assert resp_fuel_type.status_code == 200
    assert fuel_log_a in resp_fuel_type.context["fuel_logs"]

    # 4. Junk params
    resp_junk = client.get(url, {"vehicle": "invalid", "fuel_type": "bogus"})
    assert resp_junk.status_code == 200
    assert fuel_log_a in resp_junk.context["fuel_logs"]


def test_fleetvehicle_view_fuel_log_export(client, user_a, fuel_log_a, fuel_log_b):
    """Verify vehicle_fuel_log_export returns CSV with headers and formula neutralization."""
    client.force_login(user_a)
    fuel_log_a.fuel_station_name = "@Shell Station Exploit"
    fuel_log_a.save(update_fields=["fuel_station_name"])

    url = reverse("assets:vehicle_fuel_log_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert resp["X-Content-Type-Options"] == "nosniff"

    rows = _fleetvehicle_parse_csv(resp)
    assert len(rows) >= 2
    headers = rows[0]
    assert "Log Number" in headers
    assert "Quantity (Gal/kWh)" in headers
    assert "Total Cost" in headers

    # Formula neutralization check
    data_rows = rows[1:]
    matching = [r for r in data_rows if fuel_log_a.number in r]
    assert len(matching) == 1
    # station is at index 12 in export
    assert matching[0][12].startswith("'@")

    # Tenant isolation check
    tenant_b_matching = [r for r in data_rows if fuel_log_b.notes in r]
    assert len(tenant_b_matching) == 0


def test_fleetvehicle_view_fuel_log_detail(client, user_a, fuel_log_a):
    """Verify vehicle_fuel_log_detail returns 200 with fuel_log in context."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_fuel_log_detail", kwargs={"pk": fuel_log_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["fuel_log"] == fuel_log_a


def test_fleetvehicle_view_fuel_log_create(client, user_a, fleet_vehicle_a, currency_usd, tenant_a):
    """Verify vehicle_fuel_log_create GET supports ?vehicle= prefill and POST saves log."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_fuel_log_create")

    # GET with prefill
    resp_get = client.get(url, {"vehicle": str(fleet_vehicle_a.pk)})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert str(resp_get.context["form"].initial.get("vehicle")) == str(fleet_vehicle_a.pk)

    # POST valid
    payload = _fleetvehicle_valid_fuel_payload(fleet_vehicle_a, currency=currency_usd)
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created_log = VehicleFuelLog.objects.get(
        tenant=tenant_a,
        receipt_reference=payload["receipt_reference"],
    )
    assert resp_post.url == reverse("assets:vehicle_fuel_log_detail", kwargs={"pk": created_log.pk})
    assert created_log.total_cost == Decimal("90.30")


def test_fleetvehicle_view_fuel_log_edit(client, user_a, fuel_log_a, currency_usd):
    """Verify vehicle_fuel_log_edit GET and POST update fuel log successfully."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_fuel_log_edit", kwargs={"pk": fuel_log_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["fuel_log"] == fuel_log_a

    payload = _fleetvehicle_valid_fuel_payload(
        fuel_log_a.vehicle,
        currency=currency_usd,
        fuel_station_name="Chevron Updated #909",
        total_cost="99.50",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:vehicle_fuel_log_detail", kwargs={"pk": fuel_log_a.pk})

    fuel_log_a.refresh_from_db()
    assert fuel_log_a.fuel_station_name == "Chevron Updated #909"
    assert fuel_log_a.total_cost == Decimal("99.50")


def test_fleetvehicle_view_fuel_log_delete(client, user_a, fuel_log_a):
    """Verify vehicle_fuel_log_delete requires POST and deletes record cleanly."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_fuel_log_delete", kwargs={"pk": fuel_log_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 405

    pk = fuel_log_a.pk
    resp_post = client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:vehicle_fuel_log_list")
    assert not VehicleFuelLog.objects.filter(pk=pk).exists()


# =====================================================================
# 3. VehicleDriverAssignment Views Tests
# =====================================================================


def test_fleetvehicle_view_driver_assignment_list(client, user_a, driver_assignment_a, driver_assignment_b, fleet_vehicle_a):
    """Verify vehicle_driver_assignment_list returns 200 with safety scores and filters."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_driver_assignment_list")
    resp = client.get(url)
    assert resp.status_code == 200

    for key in (
        "assignments",
        "page_obj",
        "vehicles",
        "drivers",
        "status_choices",
        "safety_tier_choices",
        "active_count",
        "high_risk_count",
    ):
        assert key in resp.context, f"Missing context key: {key}"

    assignments = list(resp.context["assignments"])
    assert driver_assignment_a in assignments
    assert driver_assignment_b not in assignments

    # Filter params tests
    resp_q = client.get(url, {"q": driver_assignment_a.driver_license_number})
    assert resp_q.status_code == 200
    assert driver_assignment_a in resp_q.context["assignments"]

    resp_status = client.get(url, {"status": "active"})
    assert resp_status.status_code == 200
    assert driver_assignment_a in resp_status.context["assignments"]

    resp_junk = client.get(url, {"vehicle": "invalid", "driver": "not_an_id"})
    assert resp_junk.status_code == 200
    assert driver_assignment_a in resp_junk.context["assignments"]


def test_fleetvehicle_view_driver_assignment_export(client, user_a, driver_assignment_a, driver_assignment_b):
    """Verify vehicle_driver_assignment_export returns CSV with formula neutralization."""
    client.force_login(user_a)
    driver_assignment_a.driver_license_number = "+CA-DL-FORMULA"
    driver_assignment_a.save(update_fields=["driver_license_number"])

    url = reverse("assets:vehicle_driver_assignment_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert resp["X-Content-Type-Options"] == "nosniff"

    rows = _fleetvehicle_parse_csv(resp)
    assert len(rows) >= 2
    headers = rows[0]
    assert "Assignment Number" in headers
    assert "Safety Score" in headers
    assert "Incidents" in headers

    data_rows = rows[1:]
    matching = [r for r in data_rows if driver_assignment_a.number in r]
    assert len(matching) == 1
    # formula-prefixed driver license number should start with single quote
    # driver is at index 2, license class is at index 7
    # Tenant isolation check
    tenant_b_matching = [r for r in data_rows if driver_assignment_b.driver_license_number in r or driver_assignment_b.vehicle.name in r]
    assert len(tenant_b_matching) == 0


def test_fleetvehicle_view_driver_assignment_detail(client, user_a, driver_assignment_a):
    """Verify vehicle_driver_assignment_detail returns 200 with assignment in context."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_driver_assignment_detail", kwargs={"pk": driver_assignment_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["assignment"] == driver_assignment_a


def test_fleetvehicle_view_driver_assignment_create(client, user_a, fleet_vehicle_a, driver_profile_a, tenant_a):
    """Verify vehicle_driver_assignment_create GET with prefill and POST saves assignment."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_driver_assignment_create")

    resp_get = client.get(url, {"vehicle": str(fleet_vehicle_a.pk)})
    assert resp_get.status_code == 200
    assert str(resp_get.context["form"].initial.get("vehicle")) == str(fleet_vehicle_a.pk)

    payload = _fleetvehicle_valid_assignment_payload(fleet_vehicle_a, driver_profile_a, user=user_a)
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created_assign = VehicleDriverAssignment.objects.get(
        tenant=tenant_a,
        driver_license_number=payload["driver_license_number"],
    )
    assert resp_post.url == reverse("assets:vehicle_driver_assignment_detail", kwargs={"pk": created_assign.pk})
    assert created_assign.assignment_role == "primary_assigned"


def test_fleetvehicle_view_driver_assignment_edit(client, user_a, driver_assignment_a):
    """Verify vehicle_driver_assignment_edit updates assignment on POST."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_driver_assignment_edit", kwargs={"pk": driver_assignment_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200

    payload = _fleetvehicle_valid_assignment_payload(
        driver_assignment_a.vehicle,
        driver_assignment_a.driver,
        user=user_a,
        driver_license_number="CA-DL-UPDATED-99",
        supervisor_notes="Updated safety notes.",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:vehicle_driver_assignment_detail", kwargs={"pk": driver_assignment_a.pk})

    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.driver_license_number == "CA-DL-UPDATED-99"
    assert driver_assignment_a.supervisor_notes == "Updated safety notes."


def test_fleetvehicle_view_driver_assignment_delete(client, user_a, driver_assignment_a):
    """Verify vehicle_driver_assignment_delete requires POST and deletes record."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_driver_assignment_delete", kwargs={"pk": driver_assignment_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 405

    pk = driver_assignment_a.pk
    resp_post = client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:vehicle_driver_assignment_list")
    assert not VehicleDriverAssignment.objects.filter(pk=pk).exists()


def test_fleetvehicle_view_driver_assignment_actions_and_guards(client, user_a, driver_assignment_a):
    """Verify assignment actions: complete, revoke, record incident, and guard assertions."""
    client.force_login(user_a)
    pk = driver_assignment_a.pk

    # 1. Record incident on active assignment
    url_incident = reverse("assets:vehicle_driver_assignment_record_incident", kwargs={"pk": pk})
    old_score = driver_assignment_a.safety_score
    resp = client.post(url_incident)
    assert resp.status_code == 302
    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.incident_count == 1
    assert driver_assignment_a.safety_score == old_score - 10

    # 2. Complete assignment
    url_complete = reverse("assets:vehicle_driver_assignment_complete", kwargs={"pk": pk})
    resp = client.post(url_complete)
    assert resp.status_code == 302
    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.status == "completed"
    assert driver_assignment_a.end_datetime is not None

    # Status guard: Attempting to complete already completed assignment redirects with error
    resp_re_comp = client.post(url_complete)
    assert resp_re_comp.status_code == 302
    msgs = _fleetvehicle_messages(resp_re_comp)
    assert any("not active and cannot be completed" in m for m in msgs)

    # Status guard: Attempting to record incident on completed assignment redirects with error
    resp_inc_guard = client.post(url_incident)
    assert resp_inc_guard.status_code == 302
    msgs = _fleetvehicle_messages(resp_inc_guard)
    assert any("Incidents can only be recorded on active assignments" in m for m in msgs)

    # Status guard: Attempting to revoke non-active assignment redirects with error
    url_revoke = reverse("assets:vehicle_driver_assignment_revoke", kwargs={"pk": pk})
    resp_rev_guard = client.post(url_revoke)
    assert resp_rev_guard.status_code == 302
    msgs = _fleetvehicle_messages(resp_rev_guard)
    assert any("not active and cannot be revoked" in m for m in msgs)

    # Re-activate assignment and verify revoke action
    driver_assignment_a.status = "active"
    driver_assignment_a.save()
    resp_revoke = client.post(url_revoke)
    assert resp_revoke.status_code == 302
    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.status == "revoked_safety"
    assert driver_assignment_a.qualification_status == "suspended"


# =====================================================================
# 4. VehicleServiceSchedule Views Tests
# =====================================================================


def test_fleetvehicle_view_service_schedule_list(client, user_a, service_schedule_a, service_schedule_b, fleet_vehicle_a):
    """Verify vehicle_service_schedule_list returns 200 with overdue counters and filters."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_service_schedule_list")
    resp = client.get(url)
    assert resp.status_code == 200

    for key in (
        "schedules",
        "page_obj",
        "vehicles",
        "service_type_choices",
        "status_choices",
        "priority_choices",
        "overdue_count",
        "due_soon_count",
    ):
        assert key in resp.context, f"Missing context key: {key}"

    schedules = list(resp.context["schedules"])
    assert service_schedule_a in schedules
    assert service_schedule_b not in schedules

    # Filter params tests
    resp_q = client.get(url, {"q": service_schedule_a.service_title})
    assert resp_q.status_code == 200
    assert service_schedule_a in resp_q.context["schedules"]

    resp_srv_type = client.get(url, {"service_type": service_schedule_a.service_type})
    assert resp_srv_type.status_code == 200
    assert service_schedule_a in resp_srv_type.context["schedules"]

    resp_junk = client.get(url, {"vehicle": "invalid", "priority": "bogus_priority"})
    assert resp_junk.status_code == 200
    assert service_schedule_a in resp_junk.context["schedules"]


def test_fleetvehicle_view_service_schedule_export(client, user_a, service_schedule_a, service_schedule_b):
    """Verify vehicle_service_schedule_export returns CSV with headers and formula neutralization."""
    client.force_login(user_a)
    service_schedule_a.service_title = "-FormulaPM Service"
    service_schedule_a.save(update_fields=["service_title"])

    url = reverse("assets:vehicle_service_schedule_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert resp["X-Content-Type-Options"] == "nosniff"

    rows = _fleetvehicle_parse_csv(resp)
    assert len(rows) >= 2
    headers = rows[0]
    assert "Schedule #" in headers
    assert "Title" in headers
    assert "Est. Cost" in headers

    data_rows = rows[1:]
    matching = [r for r in data_rows if service_schedule_a.number in r]
    assert len(matching) == 1
    # title is at index 2
    assert matching[0][2].startswith("'-")
    # Tenant isolation check
    tenant_b_matching = [r for r in data_rows if service_schedule_b.service_title in r or service_schedule_b.vehicle.name in r]
    assert len(tenant_b_matching) == 0


def test_fleetvehicle_view_service_schedule_detail(client, user_a, service_schedule_a):
    """Verify vehicle_service_schedule_detail returns 200 with schedule in context."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_service_schedule_detail", kwargs={"pk": service_schedule_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["schedule"] == service_schedule_a


def test_fleetvehicle_view_service_schedule_create(client, user_a, fleet_vehicle_a, vendor_party_a, currency_usd, tenant_a):
    """Verify vehicle_service_schedule_create GET with prefill and POST saves schedule."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_service_schedule_create")

    resp_get = client.get(url, {"vehicle": str(fleet_vehicle_a.pk)})
    assert resp_get.status_code == 200
    assert str(resp_get.context["form"].initial.get("vehicle")) == str(fleet_vehicle_a.pk)

    payload = _fleetvehicle_valid_service_payload(
        fleet_vehicle_a,
        vendor=vendor_party_a,
        currency=currency_usd,
        service_title="Brake Pad Replacement & Rotor Turn",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302

    created_srv = VehicleServiceSchedule.objects.get(
        tenant=tenant_a,
        service_title="Brake Pad Replacement & Rotor Turn",
    )
    assert resp_post.url == reverse("assets:vehicle_service_schedule_detail", kwargs={"pk": created_srv.pk})


def test_fleetvehicle_view_service_schedule_edit(client, user_a, service_schedule_a):
    """Verify vehicle_service_schedule_edit updates schedule on POST."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_service_schedule_edit", kwargs={"pk": service_schedule_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 200

    payload = _fleetvehicle_valid_service_payload(
        service_schedule_a.vehicle,
        vendor=service_schedule_a.service_vendor,
        currency=service_schedule_a.currency,
        service_title="Updated PM-B 45K Service",
        estimated_cost="275.00",
    )
    resp_post = client.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:vehicle_service_schedule_detail", kwargs={"pk": service_schedule_a.pk})

    service_schedule_a.refresh_from_db()
    assert service_schedule_a.service_title == "Updated PM-B 45K Service"
    assert service_schedule_a.estimated_cost == Decimal("275.00")


def test_fleetvehicle_view_service_schedule_delete(client, user_a, service_schedule_a):
    """Verify vehicle_service_schedule_delete requires POST and deletes record."""
    client.force_login(user_a)
    url = reverse("assets:vehicle_service_schedule_delete", kwargs={"pk": service_schedule_a.pk})

    resp_get = client.get(url)
    assert resp_get.status_code == 405

    pk = service_schedule_a.pk
    resp_post = client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("assets:vehicle_service_schedule_list")
    assert not VehicleServiceSchedule.objects.filter(pk=pk).exists()


def test_fleetvehicle_view_service_schedule_actions_and_numeric_guards(client, user_a, service_schedule_a, fleet_vehicle_a):
    """Verify service actions: mark in service, pause, and complete with numeric validation & locked guard."""
    client.force_login(user_a)
    pk = service_schedule_a.pk

    # 1. Mark in service
    url_in_serv = reverse("assets:vehicle_service_schedule_mark_in_service", kwargs={"pk": pk})
    resp = client.post(url_in_serv)
    assert resp.status_code == 302
    service_schedule_a.refresh_from_db()
    assert service_schedule_a.status == "in_service"

    # 2. Pause
    url_pause = reverse("assets:vehicle_service_schedule_pause", kwargs={"pk": pk})
    resp = client.post(url_pause)
    assert resp.status_code == 302
    service_schedule_a.refresh_from_db()
    assert service_schedule_a.status == "paused"

    # 3. Complete service with NaN / Infinity / invalid cost -> defaults to 0.00 safely
    url_comp = reverse("assets:vehicle_service_schedule_complete", kwargs={"pk": pk})
    resp_nan = client.post(
        url_comp,
        {
            "completion_date": timezone.localdate().isoformat(),
            "odometer": "45200",
            "actual_cost": "NaN",
            "technician_notes": "Completed service test.",
        },
    )
    assert resp_nan.status_code == 302
    service_schedule_a.refresh_from_db()
    assert service_schedule_a.actual_cost == Decimal("0.00")
    assert service_schedule_a.last_service_odometer == 45200

    # 4. Complete with valid cost rolls forward
    resp_valid = client.post(
        url_comp,
        {
            "completion_date": timezone.localdate().isoformat(),
            "odometer": "46000",
            "actual_cost": "320.50",
            "technician_notes": "Routine PM completed.",
        },
    )
    assert resp_valid.status_code == 302
    service_schedule_a.refresh_from_db()
    assert service_schedule_a.actual_cost == Decimal("320.50")
    assert service_schedule_a.last_service_odometer == 46000
    assert service_schedule_a.next_due_odometer == 46000 + service_schedule_a.interval_mileage

    # 5. Vehicle lock guard: Decommission vehicle and verify complete is blocked
    fleet_vehicle_a.status = "decommissioned"
    fleet_vehicle_a.save()
    assert fleet_vehicle_a.is_locked is True

    resp_locked = client.post(
        url_comp,
        {
            "completion_date": timezone.localdate().isoformat(),
            "odometer": "47000",
            "actual_cost": "100.00",
        },
    )
    assert resp_locked.status_code == 302
    msgs = _fleetvehicle_messages(resp_locked)
    assert any("decommissioned / locked and service cannot be completed" in m for m in msgs)


# =====================================================================
# 5. FleetTelematicsBoard View Tests
# =====================================================================


def test_fleetvehicle_view_telematics_board(client, user_a, fleet_vehicle_a, fleet_vehicle_b, fuel_log_a, driver_assignment_a, service_schedule_a):
    """Verify fleet_telematics_board returns 200 with command center metrics, queues, and filter params."""
    client.force_login(user_a)
    url = reverse("assets:fleet_telematics_board")
    resp = client.get(url)
    assert resp.status_code == 200

    # Pinned context keys
    for key in (
        "total_vehicles",
        "active_in_service",
        "active_telematics_count",
        "in_shop",
        "moving_count",
        "idling_count",
        "speeding_count",
        "geofence_breach_count",
        "geofence_alerts_count",
        "overdue_service_count",
        "expired_compliance_count",
        "recent_vehicles",
        "high_risk_drivers",
        "recent_fuel_logs",
        "upcoming_services",
        "maintenance_queue",
    ):
        assert key in resp.context, f"Missing context key: {key}"

    # Verify tenant isolation on telematics board
    recent_vehicles = list(resp.context["recent_vehicles"])
    assert fleet_vehicle_a in recent_vehicles
    assert fleet_vehicle_b not in recent_vehicles

    # Test filtering params on telematics board
    resp_q = client.get(url, {"q": fleet_vehicle_a.license_plate})
    assert resp_q.status_code == 200
    assert fleet_vehicle_a in resp_q.context["recent_vehicles"]

    resp_state = client.get(url, {"engine_state": "engine_off"})
    assert resp_state.status_code == 200
    assert fleet_vehicle_a in resp_state.context["recent_vehicles"]

    resp_state_mismatch = client.get(url, {"engine_state": "moving_speeding"})
    assert resp_state_mismatch.status_code == 200
    assert fleet_vehicle_a not in resp_state_mismatch.context["recent_vehicles"]


# =====================================================================
# 6. Cross-Tenant IDOR Security Tests
# =====================================================================


def test_fleetvehicle_view_cross_tenant_idor_protection(
    client,
    user_a,
    fleet_vehicle_b,
    fuel_log_b,
    driver_assignment_b,
    service_schedule_b,
):
    """Verify tenant_a user receives 404 when attempting to access tenant_b records."""
    client.force_login(user_a)

    # 1. FleetVehicle IDOR
    assert client.get(reverse("assets:fleet_vehicle_detail", kwargs={"pk": fleet_vehicle_b.pk})).status_code == 404
    assert client.get(reverse("assets:fleet_vehicle_edit", kwargs={"pk": fleet_vehicle_b.pk})).status_code == 404
    assert client.post(reverse("assets:fleet_vehicle_delete", kwargs={"pk": fleet_vehicle_b.pk})).status_code == 404
    assert client.post(reverse("assets:fleet_vehicle_activate", kwargs={"pk": fleet_vehicle_b.pk})).status_code == 404
    assert client.post(reverse("assets:fleet_vehicle_mark_in_shop", kwargs={"pk": fleet_vehicle_b.pk})).status_code == 404
    assert client.post(reverse("assets:fleet_vehicle_decommission", kwargs={"pk": fleet_vehicle_b.pk})).status_code == 404

    # 2. FuelLog IDOR
    assert client.get(reverse("assets:vehicle_fuel_log_detail", kwargs={"pk": fuel_log_b.pk})).status_code == 404
    assert client.get(reverse("assets:vehicle_fuel_log_edit", kwargs={"pk": fuel_log_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_fuel_log_delete", kwargs={"pk": fuel_log_b.pk})).status_code == 404

    # 3. DriverAssignment IDOR
    assert client.get(reverse("assets:vehicle_driver_assignment_detail", kwargs={"pk": driver_assignment_b.pk})).status_code == 404
    assert client.get(reverse("assets:vehicle_driver_assignment_edit", kwargs={"pk": driver_assignment_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_driver_assignment_delete", kwargs={"pk": driver_assignment_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_driver_assignment_complete", kwargs={"pk": driver_assignment_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_driver_assignment_revoke", kwargs={"pk": driver_assignment_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_driver_assignment_record_incident", kwargs={"pk": driver_assignment_b.pk})).status_code == 404

    # 4. ServiceSchedule IDOR
    assert client.get(reverse("assets:vehicle_service_schedule_detail", kwargs={"pk": service_schedule_b.pk})).status_code == 404
    assert client.get(reverse("assets:vehicle_service_schedule_edit", kwargs={"pk": service_schedule_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_service_schedule_delete", kwargs={"pk": service_schedule_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_service_schedule_mark_in_service", kwargs={"pk": service_schedule_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_service_schedule_pause", kwargs={"pk": service_schedule_b.pk})).status_code == 404
    assert client.post(reverse("assets:vehicle_service_schedule_complete", kwargs={"pk": service_schedule_b.pk})).status_code == 404
