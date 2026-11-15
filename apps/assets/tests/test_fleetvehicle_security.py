"""
Security and Multi-Tenant Isolation Tests for Module 11.19: Fleet & Vehicle Management.

Covers:
1. Multi-Tenant IDOR:
   - Tenant A client requesting Tenant B records (detail, edit, delete, actions) returns HTTP 404.
   - Symmetric: Tenant B client requesting Tenant A records returns HTTP 404.
   - Cross-tenant mutations do not affect database state.
   - List views and telematics command board strictly isolate tenant data.
2. Unauthenticated Access:
   - Anonymous client requests to all static, object, action, board, and export endpoints redirect to login (HTTP 302).
3. Tenant Admin Privileges (@tenant_admin_required):
   - Non-admin member users attempting delete views or privileged actions (decommission, revoke, complete_service)
     receive HTTP 403 Forbidden.
   - Tenant admin users succeed (HTTP 302).
4. POST-Only Enforcement (@require_POST):
   - Sending GET to delete or state action endpoints returns HTTP 405 Method Not Allowed.
5. Cross-Tenant Form Injection (reject_foreign):
   - Submitting foreign FK IDs (vehicle, driver, vendor, user, org_unit) fails form validation and view creation.
6. CSV Export Isolation & Formula Neutralization:
   - CSV export streams only the authenticated tenant's rows (zero foreign rows).
   - Spreadsheet formula prefixes (=, +, -, @) are sanitized with a leading single-quote.
   - Headers include attachment disposition and X-Content-Type-Options: nosniff.
7. Superuser with tenant=None:
   - Global platform superuser sees 0 tenant records on list pages and telematics board (by design).
   - Object detail returns 404; CSV exports contain only headers.
8. Mass Assignment / Immutable Fields:
   - POST body tampering on tenant, number, and timestamps is ignored or overridden by server logic.
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.assets.forms.FleetVehicleManagement.FleetVehicles import FleetVehicleForm
from apps.assets.forms.FleetVehicleManagement.VehicleDriverAssignments import (
    VehicleDriverAssignmentForm,
)
from apps.assets.forms.FleetVehicleManagement.VehicleFuelLogs import (
    VehicleFuelLogForm,
)
from apps.assets.forms.FleetVehicleManagement.VehicleServiceSchedules import (
    VehicleServiceScheduleForm,
)
from apps.assets.models import (
    FleetVehicle,
    VehicleDriverAssignment,
    VehicleFuelLog,
    VehicleServiceSchedule,
)

User = get_user_model()
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


def _fleetvehicle_superuser_client():
    """Create and return a platform superuser with tenant=None and an authenticated Client."""
    su = User.objects.create_superuser(
        email="platform_super_fleet_sec@naverp.test",
        username="platform_super_fleet_sec",
        password="TestPass123!",
        tenant=None,
    )
    client = Client()
    client.force_login(su)
    return su, client


def _fleetvehicle_valid_vehicle_payload(**overrides):
    """Build a valid payload for FleetVehicle create/edit POST requests."""
    today = timezone.localdate()
    data = {
        "name": "Cargo Van Security 401",
        "vin": "1FTNE3Y89PKB88888",
        "license_plate": "SEC-401",
        "registration_state": "CA",
        "make": "Ford",
        "model": "Transit 250",
        "year": 2024,
        "vehicle_type": "cargo_van",
        "fuel_type": "gasoline",
        "ownership_type": "owned",
        "title_number": "TIT-SEC-401",
        "registration_expiration_date": (today + timedelta(days=365)).isoformat(),
        "safety_inspection_due_date": (today + timedelta(days=180)).isoformat(),
        "emissions_inspection_due_date": (today + timedelta(days=365)).isoformat(),
        "current_odometer": 15000,
        "engine_hours": "350.00",
        "gross_vehicle_weight_rating_lbs": 9070,
        "fuel_tank_capacity_gallons": "25.00",
        "is_telematics_enabled": True,
        "telematics_device_id": "TEL-SEC-401",
        "notes": "Route security delivery van.",
    }
    data.update(overrides)
    return data


def _fleetvehicle_valid_fuel_payload(vehicle, currency=None, **overrides):
    """Build a valid payload for VehicleFuelLog create/edit POST requests."""
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
    """Build a valid payload for VehicleDriverAssignment create/edit POST requests."""
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
    """Build a valid payload for VehicleServiceSchedule create/edit POST requests."""
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
# 1. Multi-Tenant IDOR Isolation
# =====================================================================


def test_fleetvehicle_security_idor_detail_edit_blocked_tenant_a_to_b(
    client_a, fleet_vehicle_b, fuel_log_b, driver_assignment_b, service_schedule_b
):
    """Tenant A client requesting Tenant B detail and edit views returns HTTP 404."""
    routes = [
        ("assets:fleet_vehicle_detail", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_edit", fleet_vehicle_b.pk),
        ("assets:vehicle_fuel_log_detail", fuel_log_b.pk),
        ("assets:vehicle_fuel_log_edit", fuel_log_b.pk),
        ("assets:vehicle_driver_assignment_detail", driver_assignment_b.pk),
        ("assets:vehicle_driver_assignment_edit", driver_assignment_b.pk),
        ("assets:vehicle_service_schedule_detail", service_schedule_b.pk),
        ("assets:vehicle_service_schedule_edit", service_schedule_b.pk),
    ]

    for url_name, pk in routes:
        # GET returns 404
        resp_get = client_a.get(reverse(url_name, args=[pk]))
        assert resp_get.status_code == 404, f"Expected 404 for GET {url_name} with foreign pk {pk}"

        # POST returns 404
        resp_post = client_a.post(reverse(url_name, args=[pk]), data={"name": "Hacked", "service_title": "Hacked"})
        assert resp_post.status_code == 404, f"Expected 404 for POST {url_name} with foreign pk {pk}"

    # Verify Tenant B records remain unchanged
    fleet_vehicle_b.refresh_from_db()
    assert fleet_vehicle_b.name == "Globex Freight Semi"
    fuel_log_b.refresh_from_db()
    assert fuel_log_b.odometer_at_fueling == 149000
    driver_assignment_b.refresh_from_db()
    assert driver_assignment_b.driver_license_number == "NV-CDL-441199"
    service_schedule_b.refresh_from_db()
    assert service_schedule_b.service_title == "Globex Annual DOT Inspection"


def test_fleetvehicle_security_idor_detail_edit_blocked_tenant_b_to_a(
    client_b, fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Symmetric: Tenant B client requesting Tenant A detail and edit views returns HTTP 404."""
    routes = [
        ("assets:fleet_vehicle_detail", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_edit", fleet_vehicle_a.pk),
        ("assets:vehicle_fuel_log_detail", fuel_log_a.pk),
        ("assets:vehicle_fuel_log_edit", fuel_log_a.pk),
        ("assets:vehicle_driver_assignment_detail", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_edit", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_detail", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_edit", service_schedule_a.pk),
    ]

    for url_name, pk in routes:
        resp_get = client_b.get(reverse(url_name, args=[pk]))
        assert resp_get.status_code == 404, f"Expected 404 for GET {url_name} with foreign pk {pk}"

        resp_post = client_b.post(reverse(url_name, args=[pk]), data={"name": "Hacked", "service_title": "Hacked"})
        assert resp_post.status_code == 404, f"Expected 404 for POST {url_name} with foreign pk {pk}"

    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.name == "Ford Transit Van 101"
    fuel_log_a.refresh_from_db()
    assert fuel_log_a.odometer_at_fueling == 42000
    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.driver_license_number == "CA-DL-992211"
    service_schedule_a.refresh_from_db()
    assert service_schedule_a.service_title == "45,000 Mile Service PM-B"


def test_fleetvehicle_security_idor_delete_and_actions_blocked_tenant_a_to_b(
    client_a, fleet_vehicle_b, fuel_log_b, driver_assignment_b, service_schedule_b
):
    """Tenant A POSTing to Tenant B delete or action endpoints returns HTTP 404 with zero state change."""
    action_routes = [
        # FleetVehicle actions & delete
        ("assets:fleet_vehicle_delete", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_activate", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_mark_in_shop", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_mark_loaner", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_mark_out_of_service", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_decommission", fleet_vehicle_b.pk),
        ("assets:fleet_vehicle_ping_telemetry", fleet_vehicle_b.pk),
        # VehicleFuelLog delete
        ("assets:vehicle_fuel_log_delete", fuel_log_b.pk),
        # VehicleDriverAssignment actions & delete
        ("assets:vehicle_driver_assignment_delete", driver_assignment_b.pk),
        ("assets:vehicle_driver_assignment_complete", driver_assignment_b.pk),
        ("assets:vehicle_driver_assignment_revoke", driver_assignment_b.pk),
        ("assets:vehicle_driver_assignment_record_incident", driver_assignment_b.pk),
        # VehicleServiceSchedule actions & delete
        ("assets:vehicle_service_schedule_delete", service_schedule_b.pk),
        ("assets:vehicle_service_schedule_complete", service_schedule_b.pk),
        ("assets:vehicle_service_schedule_mark_in_service", service_schedule_b.pk),
        ("assets:vehicle_service_schedule_pause", service_schedule_b.pk),
    ]

    for url_name, pk in action_routes:
        resp = client_a.post(reverse(url_name, args=[pk]))
        assert resp.status_code == 404, f"Expected 404 for POST {url_name} with foreign pk {pk}"

    # Verify all Tenant B objects still exist and are untouched
    assert FleetVehicle.objects.filter(pk=fleet_vehicle_b.pk).exists()
    fleet_vehicle_b.refresh_from_db()
    assert fleet_vehicle_b.status == "active_in_service"

    assert VehicleFuelLog.objects.filter(pk=fuel_log_b.pk).exists()

    assert VehicleDriverAssignment.objects.filter(pk=driver_assignment_b.pk).exists()
    driver_assignment_b.refresh_from_db()
    assert driver_assignment_b.status == "active"
    assert driver_assignment_b.incident_count == 0

    assert VehicleServiceSchedule.objects.filter(pk=service_schedule_b.pk).exists()
    service_schedule_b.refresh_from_db()
    assert service_schedule_b.status == "due_soon"


def test_fleetvehicle_security_idor_delete_and_actions_blocked_tenant_b_to_a(
    client_b, fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Symmetric: Tenant B POSTing to Tenant A delete or action endpoints returns HTTP 404."""
    action_routes = [
        ("assets:fleet_vehicle_delete", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_activate", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_in_shop", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_loaner", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_out_of_service", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_decommission", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_ping_telemetry", fleet_vehicle_a.pk),
        ("assets:vehicle_fuel_log_delete", fuel_log_a.pk),
        ("assets:vehicle_driver_assignment_delete", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_complete", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_revoke", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_record_incident", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_delete", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_complete", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_mark_in_service", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_pause", service_schedule_a.pk),
    ]

    for url_name, pk in action_routes:
        resp = client_b.post(reverse(url_name, args=[pk]))
        assert resp.status_code == 404, f"Expected 404 for POST {url_name} with foreign pk {pk}"

    assert FleetVehicle.objects.filter(pk=fleet_vehicle_a.pk).exists()
    assert VehicleFuelLog.objects.filter(pk=fuel_log_a.pk).exists()
    assert VehicleDriverAssignment.objects.filter(pk=driver_assignment_a.pk).exists()
    assert VehicleServiceSchedule.objects.filter(pk=service_schedule_a.pk).exists()


def test_fleetvehicle_security_list_views_and_board_tenant_isolation(
    client_a, client_b, fleet_vehicle_a, fleet_vehicle_b, fuel_log_a, fuel_log_b,
    driver_assignment_a, driver_assignment_b, service_schedule_a, service_schedule_b
):
    """List views and telematics command board strictly isolate tenant records."""
    # 1. Vehicle list (distinguish by unique license plate)
    resp_v_a = client_a.get(reverse("assets:fleet_vehicle_list"))
    assert resp_v_a.status_code == 200
    assert fleet_vehicle_a.license_plate in resp_v_a.content.decode("utf-8")
    assert fleet_vehicle_b.license_plate not in resp_v_a.content.decode("utf-8")

    resp_v_b = client_b.get(reverse("assets:fleet_vehicle_list"))
    assert resp_v_b.status_code == 200
    assert fleet_vehicle_b.license_plate in resp_v_b.content.decode("utf-8")
    assert fleet_vehicle_a.license_plate not in resp_v_b.content.decode("utf-8")

    # 2. Fuel log list (distinguish by station name / notes)
    resp_f_a = client_a.get(reverse("assets:vehicle_fuel_log_list"))
    assert resp_f_a.status_code == 200
    assert fuel_log_a.fuel_station_name in resp_f_a.content.decode("utf-8")
    assert "Globex diesel refill" not in resp_f_a.content.decode("utf-8")

    # 3. Driver assignment list (distinguish by driver license number)
    resp_d_a = client_a.get(reverse("assets:vehicle_driver_assignment_list"))
    assert resp_d_a.status_code == 200
    assert driver_assignment_a.driver_license_number in resp_d_a.content.decode("utf-8")
    assert driver_assignment_b.driver_license_number not in resp_d_a.content.decode("utf-8")

    # 4. Service schedule list (distinguish by service title)
    resp_s_a = client_a.get(reverse("assets:vehicle_service_schedule_list"))
    assert resp_s_a.status_code == 200
    assert service_schedule_a.service_title in resp_s_a.content.decode("utf-8")
    assert service_schedule_b.service_title not in resp_s_a.content.decode("utf-8")

    # 5. Telematics board
    resp_board_a = client_a.get(reverse("assets:fleet_telematics_board"))
    assert resp_board_a.status_code == 200
    board_a_html = resp_board_a.content.decode("utf-8")
    assert fleet_vehicle_a.name in board_a_html
    assert fleet_vehicle_b.name not in board_a_html
    assert resp_board_a.context["total_vehicles"] == 1

    resp_board_b = client_b.get(reverse("assets:fleet_telematics_board"))
    assert resp_board_b.status_code == 200
    board_b_html = resp_board_b.content.decode("utf-8")
    assert fleet_vehicle_b.name in board_b_html
    assert fleet_vehicle_a.name not in board_b_html
    assert resp_board_b.context["total_vehicles"] == 1


# =====================================================================
# 2. Unauthenticated Access (@login_required)
# =====================================================================


@pytest.mark.parametrize(
    "url_name",
    [
        "assets:fleet_vehicle_list",
        "assets:fleet_vehicle_export",
        "assets:fleet_vehicle_create",
        "assets:vehicle_fuel_log_list",
        "assets:vehicle_fuel_log_export",
        "assets:vehicle_fuel_log_create",
        "assets:vehicle_driver_assignment_list",
        "assets:vehicle_driver_assignment_export",
        "assets:vehicle_driver_assignment_create",
        "assets:vehicle_service_schedule_list",
        "assets:vehicle_service_schedule_export",
        "assets:vehicle_service_schedule_create",
        "assets:fleet_telematics_board",
    ],
)
def test_fleetvehicle_security_unauthenticated_static_routes_redirect_to_login(url_name):
    """Anonymous GET requests to static routes redirect to login (HTTP 302)."""
    anon = Client()
    resp = anon.get(reverse(url_name))
    assert resp.status_code == 302
    assert "login" in resp.url


def test_fleetvehicle_security_unauthenticated_object_routes_redirect_to_login(
    fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Anonymous GET and POST requests to detail and edit views redirect to login (HTTP 302)."""
    anon = Client()
    object_routes = [
        ("assets:fleet_vehicle_detail", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_edit", fleet_vehicle_a.pk),
        ("assets:vehicle_fuel_log_detail", fuel_log_a.pk),
        ("assets:vehicle_fuel_log_edit", fuel_log_a.pk),
        ("assets:vehicle_driver_assignment_detail", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_edit", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_detail", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_edit", service_schedule_a.pk),
    ]

    for url_name, pk in object_routes:
        resp_get = anon.get(reverse(url_name, args=[pk]))
        assert resp_get.status_code == 302
        assert "login" in resp_get.url

        resp_post = anon.post(reverse(url_name, args=[pk]), data={})
        assert resp_post.status_code == 302
        assert "login" in resp_post.url


def test_fleetvehicle_security_unauthenticated_post_create_redirects_to_login():
    """Anonymous POST to create endpoints redirects to login and creates nothing."""
    anon = Client()
    create_urls = [
        "assets:fleet_vehicle_create",
        "assets:vehicle_fuel_log_create",
        "assets:vehicle_driver_assignment_create",
        "assets:vehicle_service_schedule_create",
    ]

    for url_name in create_urls:
        resp = anon.post(reverse(url_name), data={"name": "Anon Vehicle"})
        assert resp.status_code == 302
        assert "login" in resp.url


def test_fleetvehicle_security_unauthenticated_post_actions_and_deletes_redirect_to_login(
    fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Anonymous POST to delete and action endpoints redirects to login with zero state changes."""
    anon = Client()
    action_routes = [
        ("assets:fleet_vehicle_delete", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_activate", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_in_shop", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_loaner", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_out_of_service", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_decommission", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_ping_telemetry", fleet_vehicle_a.pk),
        ("assets:vehicle_fuel_log_delete", fuel_log_a.pk),
        ("assets:vehicle_driver_assignment_delete", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_complete", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_revoke", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_record_incident", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_delete", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_complete", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_mark_in_service", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_pause", service_schedule_a.pk),
    ]

    for url_name, pk in action_routes:
        resp = anon.post(reverse(url_name, args=[pk]))
        assert resp.status_code == 302
        assert "login" in resp.url

    # Verify all records untouched
    assert FleetVehicle.objects.filter(pk=fleet_vehicle_a.pk).exists()
    assert VehicleFuelLog.objects.filter(pk=fuel_log_a.pk).exists()
    assert VehicleDriverAssignment.objects.filter(pk=driver_assignment_a.pk).exists()
    assert VehicleServiceSchedule.objects.filter(pk=service_schedule_a.pk).exists()


# =====================================================================
# 3. Tenant Admin Privileges (@tenant_admin_required)
# =====================================================================


def test_fleetvehicle_security_tenant_admin_required_delete_views_reject_non_admin(
    member_client, fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Non-admin member user attempting delete views receives HTTP 403 Forbidden."""
    delete_endpoints = [
        ("assets:fleet_vehicle_delete", fleet_vehicle_a.pk),
        ("assets:vehicle_fuel_log_delete", fuel_log_a.pk),
        ("assets:vehicle_driver_assignment_delete", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_delete", service_schedule_a.pk),
    ]

    for url_name, pk in delete_endpoints:
        resp = member_client.post(reverse(url_name, args=[pk]))
        assert resp.status_code == 403, f"Expected 403 Forbidden for non-admin on {url_name}"

    # Verify records were NOT deleted
    assert FleetVehicle.objects.filter(pk=fleet_vehicle_a.pk).exists()
    assert VehicleFuelLog.objects.filter(pk=fuel_log_a.pk).exists()
    assert VehicleDriverAssignment.objects.filter(pk=driver_assignment_a.pk).exists()
    assert VehicleServiceSchedule.objects.filter(pk=service_schedule_a.pk).exists()


def test_fleetvehicle_security_tenant_admin_required_action_views_reject_non_admin(
    member_client, fleet_vehicle_a, driver_assignment_a, service_schedule_a
):
    """Non-admin member user attempting privileged actions (decommission, revoke, complete) receives HTTP 403."""
    privileged_actions = [
        ("assets:fleet_vehicle_decommission", fleet_vehicle_a.pk),
        ("assets:vehicle_driver_assignment_revoke", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_complete", service_schedule_a.pk),
    ]

    for url_name, pk in privileged_actions:
        resp = member_client.post(reverse(url_name, args=[pk]))
        assert resp.status_code == 403, f"Expected 403 Forbidden for non-admin on {url_name}"

    # Verify states remain unmodified
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status != "decommissioned"

    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.status != "revoked_safety"
    assert driver_assignment_a.qualification_status != "suspended"

    service_schedule_a.refresh_from_db()
    assert service_schedule_a.status != "completed"


def test_fleetvehicle_security_tenant_admin_allowed_privileged_actions(
    client_a, fleet_vehicle_a, driver_assignment_a, service_schedule_a, tenant_a
):
    """Tenant admin user succeeds when executing privileged actions and delete operations."""
    # 1. Complete service schedule (executed while vehicle is still in active service)
    resp_complete = client_a.post(
        reverse("assets:vehicle_service_schedule_complete", args=[service_schedule_a.pk]),
        data={
            "completion_date": timezone.localdate().isoformat(),
            "odometer": "45000",
            "actual_cost": "210.00",
            "technician_notes": "Completed by certified technician.",
        },
    )
    assert resp_complete.status_code == 302
    service_schedule_a.refresh_from_db()
    assert service_schedule_a.actual_cost == Decimal("210.00")

    # 2. Revoke driver assignment
    resp_revoke = client_a.post(reverse("assets:vehicle_driver_assignment_revoke", args=[driver_assignment_a.pk]))
    assert resp_revoke.status_code == 302
    driver_assignment_a.refresh_from_db()
    assert driver_assignment_a.status == "revoked_safety"
    assert driver_assignment_a.qualification_status == "suspended"

    # 3. Decommission vehicle
    resp_decomm = client_a.post(reverse("assets:fleet_vehicle_decommission", args=[fleet_vehicle_a.pk]))
    assert resp_decomm.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.status == "decommissioned"

    # 4. Delete operation succeeds for tenant admin
    extra_veh = FleetVehicle.objects.create(
        tenant=tenant_a,
        name="Deletable Fleet Vehicle",
        vin="1FTNE3Y89PKB99999",
        license_plate="DEL-999",
        registration_state="CA",
        make="Ford",
        model="Transit",
        year=2023,
    )
    resp_del = client_a.post(reverse("assets:fleet_vehicle_delete", args=[extra_veh.pk]))
    assert resp_del.status_code == 302
    assert not FleetVehicle.objects.filter(pk=extra_veh.pk).exists()


# =====================================================================
# 4. POST-Only Enforcement (@require_POST)
# =====================================================================


def test_fleetvehicle_security_require_post_enforced_on_all_action_and_delete_endpoints(
    client_a, fleet_vehicle_a, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Sending GET to delete or state action endpoints returns HTTP 405 Method Not Allowed."""
    post_only_routes = [
        # FleetVehicle (1 delete + 6 actions)
        ("assets:fleet_vehicle_delete", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_activate", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_in_shop", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_loaner", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_mark_out_of_service", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_decommission", fleet_vehicle_a.pk),
        ("assets:fleet_vehicle_ping_telemetry", fleet_vehicle_a.pk),
        # VehicleFuelLog (1 delete)
        ("assets:vehicle_fuel_log_delete", fuel_log_a.pk),
        # VehicleDriverAssignment (1 delete + 3 actions)
        ("assets:vehicle_driver_assignment_delete", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_complete", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_revoke", driver_assignment_a.pk),
        ("assets:vehicle_driver_assignment_record_incident", driver_assignment_a.pk),
        # VehicleServiceSchedule (1 delete + 3 actions)
        ("assets:vehicle_service_schedule_delete", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_complete", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_mark_in_service", service_schedule_a.pk),
        ("assets:vehicle_service_schedule_pause", service_schedule_a.pk),
    ]

    for url_name, pk in post_only_routes:
        resp = client_a.get(reverse(url_name, args=[pk]))
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url_name}"


# =====================================================================
# 5. Cross-Tenant Form Injection (reject_foreign)
# =====================================================================


def test_fleetvehicle_security_cross_tenant_fk_injection_fleet_vehicle(
    client_a, tenant_a, org_unit_b, driver_profile_b, vendor_party_b
):
    """Submitting foreign org_unit, primary_driver, or custodian_party from Tenant B fails validation."""
    create_url = reverse("assets:fleet_vehicle_create")

    # 1. Foreign org_unit
    p1 = _fleetvehicle_valid_vehicle_payload(
        name="Cross-Tenant OrgUnit Vehicle",
        vin="1FTNE3Y89PKB11111",
        license_plate="INJ-001",
        org_unit=str(org_unit_b.pk),
    )
    resp1 = client_a.post(create_url, p1)
    assert resp1.status_code == 200
    assert not FleetVehicle.objects.filter(tenant=tenant_a, license_plate="INJ-001").exists()

    # Direct form verification via reject_foreign
    form1 = FleetVehicleForm(p1, tenant=tenant_a)
    assert form1.is_valid() is False
    assert "org_unit" in form1.errors

    # 2. Foreign primary driver
    p2 = _fleetvehicle_valid_vehicle_payload(
        name="Cross-Tenant Driver Vehicle",
        vin="1FTNE3Y89PKB22222",
        license_plate="INJ-002",
        primary_driver=str(driver_profile_b.pk),
    )
    resp2 = client_a.post(create_url, p2)
    assert resp2.status_code == 200
    assert not FleetVehicle.objects.filter(tenant=tenant_a, license_plate="INJ-002").exists()

    form2 = FleetVehicleForm(p2, tenant=tenant_a)
    assert form2.is_valid() is False
    assert "primary_driver" in form2.errors

    # 3. Foreign custodian party
    p3 = _fleetvehicle_valid_vehicle_payload(
        name="Cross-Tenant Custodian Vehicle",
        vin="1FTNE3Y89PKB33333",
        license_plate="INJ-003",
        custodian_party=str(vendor_party_b.pk),
    )
    resp3 = client_a.post(create_url, p3)
    assert resp3.status_code == 200
    assert not FleetVehicle.objects.filter(tenant=tenant_a, license_plate="INJ-003").exists()

    form3 = FleetVehicleForm(p3, tenant=tenant_a)
    assert form3.is_valid() is False
    assert "custodian_party" in form3.errors


def test_fleetvehicle_security_cross_tenant_fk_injection_fuel_log(
    client_a, tenant_a, fleet_vehicle_a, fleet_vehicle_b, driver_profile_b, vendor_party_b, currency_usd
):
    """Submitting foreign vehicle, driver, or fuel_vendor from Tenant B fails validation."""
    create_url = reverse("assets:vehicle_fuel_log_create")

    # 1. Foreign vehicle
    p1 = _fleetvehicle_valid_fuel_payload(fleet_vehicle_b, currency=currency_usd)
    resp1 = client_a.post(create_url, p1)
    assert resp1.status_code == 200
    assert not VehicleFuelLog.objects.filter(tenant=tenant_a, vehicle=fleet_vehicle_b).exists()

    form1 = VehicleFuelLogForm(p1, tenant=tenant_a)
    assert form1.is_valid() is False
    assert "vehicle" in form1.errors

    # 2. Foreign driver
    p2 = _fleetvehicle_valid_fuel_payload(fleet_vehicle_a, currency=currency_usd, driver=str(driver_profile_b.pk))
    resp2 = client_a.post(create_url, p2)
    assert resp2.status_code == 200
    assert not VehicleFuelLog.objects.filter(tenant=tenant_a, driver=driver_profile_b).exists()

    form2 = VehicleFuelLogForm(p2, tenant=tenant_a)
    assert form2.is_valid() is False
    assert "driver" in form2.errors

    # 3. Foreign fuel vendor
    p3 = _fleetvehicle_valid_fuel_payload(fleet_vehicle_a, currency=currency_usd, fuel_vendor=str(vendor_party_b.pk))
    resp3 = client_a.post(create_url, p3)
    assert resp3.status_code == 200
    assert not VehicleFuelLog.objects.filter(tenant=tenant_a, fuel_vendor=vendor_party_b).exists()

    form3 = VehicleFuelLogForm(p3, tenant=tenant_a)
    assert form3.is_valid() is False
    assert "fuel_vendor" in form3.errors


def test_fleetvehicle_security_cross_tenant_fk_injection_driver_assignment(
    client_a, tenant_a, fleet_vehicle_a, fleet_vehicle_b, driver_profile_b, user_b
):
    """Submitting foreign vehicle, driver, or user from Tenant B fails validation."""
    create_url = reverse("assets:vehicle_driver_assignment_create")

    # 1. Foreign vehicle
    p1 = _fleetvehicle_valid_assignment_payload(fleet_vehicle_b, driver=driver_profile_b)
    resp1 = client_a.post(create_url, p1)
    assert resp1.status_code == 200
    assert not VehicleDriverAssignment.objects.filter(tenant=tenant_a, vehicle=fleet_vehicle_b).exists()

    form1 = VehicleDriverAssignmentForm(p1, tenant=tenant_a)
    assert form1.is_valid() is False
    assert "vehicle" in form1.errors

    # 2. Foreign driver profile
    p2 = _fleetvehicle_valid_assignment_payload(fleet_vehicle_a, driver=driver_profile_b)
    resp2 = client_a.post(create_url, p2)
    assert resp2.status_code == 200
    assert not VehicleDriverAssignment.objects.filter(tenant=tenant_a, driver=driver_profile_b).exists()

    form2 = VehicleDriverAssignmentForm(p2, tenant=tenant_a)
    assert form2.is_valid() is False
    assert "driver" in form2.errors

    # 3. Foreign user
    p3 = _fleetvehicle_valid_assignment_payload(fleet_vehicle_a, driver=fleet_vehicle_a.primary_driver, user=user_b)
    resp3 = client_a.post(create_url, p3)
    assert resp3.status_code == 200
    assert not VehicleDriverAssignment.objects.filter(tenant=tenant_a, user=user_b).exists()

    form3 = VehicleDriverAssignmentForm(p3, tenant=tenant_a)
    assert form3.is_valid() is False
    assert "user" in form3.errors


def test_fleetvehicle_security_cross_tenant_fk_injection_service_schedule(
    client_a, tenant_a, fleet_vehicle_a, fleet_vehicle_b, vendor_party_b, currency_usd
):
    """Submitting foreign vehicle or service_vendor from Tenant B fails validation."""
    create_url = reverse("assets:vehicle_service_schedule_create")

    # 1. Foreign vehicle
    p1 = _fleetvehicle_valid_service_payload(fleet_vehicle_b, currency=currency_usd)
    resp1 = client_a.post(create_url, p1)
    assert resp1.status_code == 200
    assert not VehicleServiceSchedule.objects.filter(tenant=tenant_a, vehicle=fleet_vehicle_b).exists()

    form1 = VehicleServiceScheduleForm(p1, tenant=tenant_a)
    assert form1.is_valid() is False
    assert "vehicle" in form1.errors

    # 2. Foreign service vendor
    p2 = _fleetvehicle_valid_service_payload(fleet_vehicle_a, vendor=vendor_party_b, currency=currency_usd)
    resp2 = client_a.post(create_url, p2)
    assert resp2.status_code == 200
    assert not VehicleServiceSchedule.objects.filter(tenant=tenant_a, service_vendor=vendor_party_b).exists()

    form2 = VehicleServiceScheduleForm(p2, tenant=tenant_a)
    assert form2.is_valid() is False
    assert "service_vendor" in form2.errors


# =====================================================================
# 6. CSV Export Isolation & Formula Neutralization
# =====================================================================


def test_fleetvehicle_security_csv_export_tenant_isolation(
    client_a, client_b, fleet_vehicle_a, fleet_vehicle_b, fuel_log_a, fuel_log_b,
    driver_assignment_a, driver_assignment_b, service_schedule_a, service_schedule_b
):
    """CSV exports stream strictly Tenant A rows, zero Tenant B rows (and vice versa)."""
    export_pairs = [
        ("assets:fleet_vehicle_export", fleet_vehicle_a.license_plate, fleet_vehicle_b.license_plate),
        ("assets:vehicle_fuel_log_export", fuel_log_a.fuel_station_name, fleet_vehicle_b.name),
        ("assets:vehicle_driver_assignment_export", "John Fleet Driver", "Jane Globex Driver"),
        ("assets:vehicle_service_schedule_export", service_schedule_a.service_title, service_schedule_b.service_title),
    ]

    for url_name, expected_unique_a, foreign_unique_b in export_pairs:
        # Tenant A export
        resp_a = client_a.get(reverse(url_name))
        assert resp_a.status_code == 200
        assert resp_a["Content-Type"].startswith("text/csv")
        assert resp_a["X-Content-Type-Options"] == "nosniff"
        rows_a = _fleetvehicle_parse_csv(resp_a)
        content_a = resp_a.content.decode("utf-8")
        assert expected_unique_a in content_a
        assert foreign_unique_b not in content_a
        # Header + 1 record row
        assert len(rows_a) == 2

        # Tenant B export
        resp_b = client_b.get(reverse(url_name))
        assert resp_b.status_code == 200
        content_b = resp_b.content.decode("utf-8")
        assert foreign_unique_b in content_b
        assert expected_unique_a not in content_b


def test_fleetvehicle_security_csv_export_formula_neutralization(
    client_a, tenant_a, fleet_vehicle_a, currency_usd
):
    """Values starting with spreadsheet formula triggers (=, +, -, @) are sanitized with a leading single quote."""
    today = timezone.localdate()
    now = timezone.now()

    # 1. Vehicle with formula injection strings
    veh = FleetVehicle.objects.create(
        tenant=tenant_a,
        name="=CMD|' /C calc'!A0",
        vin="1FTNE3Y89PKB77777",
        license_plate="@EXEC",
        registration_state="CA",
        make="+FORMULA",
        model="-DANGEROUS",
        year=2024,
    )

    resp_veh = client_a.get(reverse("assets:fleet_vehicle_export"))
    rows_veh = _fleetvehicle_parse_csv(resp_veh)
    veh_row = next(r for r in rows_veh if r[0] == veh.number)
    # Name column: neutralized
    assert veh_row[1] == "'=CMD|' /C calc'!A0"
    # License Plate column: neutralized
    assert veh_row[2] == "'@EXEC"
    # Make column: neutralized
    assert veh_row[4] == "'+FORMULA"
    # Model column: neutralized
    assert veh_row[5] == "'-DANGEROUS"

    # 2. Fuel Log with formula injection in station name
    fuel = VehicleFuelLog.objects.create(
        tenant=tenant_a,
        vehicle=fleet_vehicle_a,
        fuel_date=now,
        odometer_at_fueling=45000,
        fuel_type="regular_gasoline",
        quantity_gallons=Decimal("15.000"),
        unit_price=Decimal("4.500"),
        total_cost=Decimal("67.50"),
        currency=currency_usd,
        fuel_station_name="=HYPERLINK(\"http://evil.com\")",
    )
    resp_fuel = client_a.get(reverse("assets:vehicle_fuel_log_export"))
    rows_fuel = _fleetvehicle_parse_csv(resp_fuel)
    fuel_row = next(r for r in rows_fuel if r[0] == fuel.number)
    assert fuel_row[12] == "'=HYPERLINK(\"http://evil.com\")"

    # 3. Driver assignment on formula-named vehicle
    assign = VehicleDriverAssignment.objects.create(
        tenant=tenant_a,
        vehicle=veh,
        driver=fleet_vehicle_a.primary_driver,
        driver_license_number="CA-DL-776655",
        driver_license_state="CA",
        start_datetime=now,
        start_odometer=45000,
    )
    resp_assign = client_a.get(reverse("assets:vehicle_driver_assignment_export"))
    rows_assign = _fleetvehicle_parse_csv(resp_assign)
    assign_row = next(r for r in rows_assign if r[0] == assign.number)
    # Vehicle name column neutralized
    assert assign_row[1] == "'=CMD|' /C calc'!A0"

    # 4. Service schedule with formula in title
    srv = VehicleServiceSchedule.objects.create(
        tenant=tenant_a,
        vehicle=fleet_vehicle_a,
        service_title="=SYSTEM(\"whoami\")",
        service_type="brake_inspection",
        currency=currency_usd,
    )
    resp_srv = client_a.get(reverse("assets:vehicle_service_schedule_export"))
    rows_srv = _fleetvehicle_parse_csv(resp_srv)
    srv_row = next(r for r in rows_srv if r[0] == srv.number)
    assert srv_row[2] == "'=SYSTEM(\"whoami\")"
    resp_srv = client_a.get(reverse("assets:vehicle_service_schedule_export"))
    rows_srv = _fleetvehicle_parse_csv(resp_srv)
    srv_row = next(r for r in rows_srv if r[0] == srv.number)
    assert srv_row[2] == "'=SYSTEM(\"whoami\")"


# =====================================================================
# 7. Superuser with tenant=None
# =====================================================================


def test_fleetvehicle_security_superuser_tenant_none_empty_lists_and_telematics_board(
    fleet_vehicle_a, fleet_vehicle_b, fuel_log_a, driver_assignment_a, service_schedule_a
):
    """Global superuser with tenant=None sees 0 tenant records in lists & board, and 404 on details."""
    _, su_client = _fleetvehicle_superuser_client()

    # 1. List views return 200 with 0 records
    list_urls = [
        "assets:fleet_vehicle_list",
        "assets:vehicle_fuel_log_list",
        "assets:vehicle_driver_assignment_list",
        "assets:vehicle_service_schedule_list",
    ]
    for url_name in list_urls:
        resp = su_client.get(reverse(url_name))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert fleet_vehicle_a.number not in content
        assert fleet_vehicle_b.number not in content

    # 2. Telematics board returns 200 with zero metrics
    resp_board = su_client.get(reverse("assets:fleet_telematics_board"))
    assert resp_board.status_code == 200
    assert resp_board.context["total_vehicles"] == 0
    assert resp_board.context["active_in_service"] == 0
    assert resp_board.context["in_shop"] == 0

    # 3. CSV exports return 1 row (header only)
    export_urls = [
        "assets:fleet_vehicle_export",
        "assets:vehicle_fuel_log_export",
        "assets:vehicle_driver_assignment_export",
        "assets:vehicle_service_schedule_export",
    ]
    for url_name in export_urls:
        resp_csv = su_client.get(reverse(url_name))
        assert resp_csv.status_code == 200
        rows = _fleetvehicle_parse_csv(resp_csv)
        assert len(rows) == 1, f"Expected header only for superuser on {url_name}"

    # 4. Detail views return 404 (assets_object scopes to tenant=request.tenant which is None)
    detail_urls = [
        ("assets:fleet_vehicle_detail", fleet_vehicle_a.pk),
        ("assets:vehicle_fuel_log_detail", fuel_log_a.pk),
        ("assets:vehicle_driver_assignment_detail", driver_assignment_a.pk),
        ("assets:vehicle_service_schedule_detail", service_schedule_a.pk),
    ]
    for url_name, pk in detail_urls:
        resp_det = su_client.get(reverse(url_name, args=[pk]))
        assert resp_det.status_code == 404, f"Expected 404 for superuser on {url_name}"


# =====================================================================
# 8. Mass Assignment & Immutable Field Tamper Resistance
# =====================================================================


def test_fleetvehicle_security_mass_assignment_tenant_and_number_tamper_resistant(
    client_a, tenant_a, tenant_b, fleet_vehicle_a
):
    """POSTing forged tenant or number cannot reassign ownership or override auto-generated numbering."""
    # 1. Attempt forge on vehicle create
    payload = _fleetvehicle_valid_vehicle_payload(
        name="Tamper Attempt Vehicle",
        vin="1FTNE3Y89PKB55555",
        license_plate="TAM-001",
        tenant=str(tenant_b.pk),
        number="FLT-FORGED-001",
    )
    resp = client_a.post(reverse("assets:fleet_vehicle_create"), payload)
    assert resp.status_code == 302
    created_veh = FleetVehicle.objects.get(tenant=tenant_a, license_plate="TAM-001")
    assert created_veh.tenant == tenant_a
    assert created_veh.number != "FLT-FORGED-001"
    assert created_veh.number.startswith("FLT-")

    # 2. Attempt forge on vehicle edit
    edit_payload = _fleetvehicle_valid_vehicle_payload(
        name="Tamper Edited Vehicle",
        vin=fleet_vehicle_a.vin,
        license_plate=fleet_vehicle_a.license_plate,
        tenant=str(tenant_b.pk),
        number="FLT-FORGED-002",
    )
    resp_edit = client_a.post(reverse("assets:fleet_vehicle_edit", args=[fleet_vehicle_a.pk]), edit_payload)
    assert resp_edit.status_code == 302
    fleet_vehicle_a.refresh_from_db()
    assert fleet_vehicle_a.tenant == tenant_a
    assert fleet_vehicle_a.number != "FLT-FORGED-002"
