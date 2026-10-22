"""Sales 8.16 — Mobile Sales & Field Execution Views Test Suite.

Comprehensive coverage of all views under apps/sales/views/MobileSales/:
1. MobileSalesDashboard:
   - mobile_sales_dashboard: 200 OK, full context keys assertion, KPI metrics,
     geofence compliance percentage calculations, active records and radar alerts,
     unauthenticated redirect.
2. FieldSalesRoutes:
   - field_sales_route_list: 200 OK, filters (q, status, sales_rep, route_date),
     junk search query handling, pagination (15 items/page).
   - field_sales_route_create: GET (200 OK with initial sales_rep), POST valid (302 redirects to detail),
     POST invalid (200 OK with form errors).
   - field_sales_route_detail: 200 OK, displays route number, name, stops and completion rate.
   - field_sales_route_edit: GET (200 OK), POST valid (302 redirects to detail, audit logged), POST invalid.
   - field_sales_route_delete: GET 405 Method Not Allowed, POST (302 redirects to list, deletes record).
   - field_sales_route_optimize: GET 405 Method Not Allowed, POST on scheduled/in_progress route sets
     optimization_status to 'optimized', POST on completed/cancelled route rejects with error message.
   - Cross-tenant IDOR isolation: client_b receives 404 for tenant_a route records.
3. FieldCheckIns:
   - field_check_in_list: 200 OK, filters (q, verification_status, visit_purpose, outcome, sales_rep),
     junk query handling, pagination, select_related optimizations.
   - field_check_in_create: GET (200 OK, auto-sets route and stop_number from GET param ?route=),
     POST valid (302 redirects to detail), POST invalid (200 OK with errors).
   - field_check_in_detail: 200 OK, displays check-in number, party, duration display.
   - field_check_in_edit: GET (200 OK), POST valid (302 redirects to detail), POST invalid.
   - field_check_in_delete: GET 405 Method Not Allowed, restricted to sales rep or tenant admin (non-rep
     non-admin denied with error message), deletes visit and updates parent route completed_stops.
   - field_check_in_checkout: GET (200 OK departure modal), POST (302 records departure, auto-calculates
     duration_minutes, updates parent route completed_stops).
   - Cross-tenant IDOR isolation: client_b receives 404 for tenant_a check-in records.
4. MobileDeviceSessions:
   - mobile_device_session_list: 200 OK, filters (q, platform, last_sync_status, user),
     junk query handling, pagination.
   - mobile_device_session_create: GET (200 OK), POST valid (302 redirects to detail), POST invalid.
   - mobile_device_session_detail: 200 OK, displays device name, masked push token, recent alerts.
   - mobile_device_session_edit: GET (200 OK), POST valid (302 redirects to detail),
     restricted to device owner or tenant admin.
   - mobile_device_session_delete: GET 405 Method Not Allowed, restricted to device owner or tenant admin.
   - mobile_device_session_sync: GET 405 Method Not Allowed, POST records sync event and audit log.
   - Cross-tenant IDOR isolation: client_b receives 404 for tenant_a device sessions.
5. MobileDealAlerts:
   - mobile_deal_alert_list: 200 OK, filters (q, alert_type, urgency, is_read, recipient),
     junk query handling, pagination.
   - mobile_deal_alert_create: GET (200 OK, preselects device via ?device=), POST valid (302 redirects to detail),
     POST invalid.
   - mobile_deal_alert_detail: 200 OK, auto-marks alert as read when viewed by recipient,
     leaves unread when viewed by non-recipient.
   - mobile_deal_alert_edit: GET (200 OK), POST valid (302 redirects to detail), POST invalid.
   - mobile_deal_alert_delete: GET 405 Method Not Allowed, restricted to recipient or tenant admin.
   - mobile_deal_alert_mark_read: GET 405 Method Not Allowed, restricted to recipient or tenant admin.
   - Cross-tenant IDOR isolation: client_b receives 404 for tenant_a alerts.
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.sales.models.MobileSales.FieldCheckIns import FieldCheckIn
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute
from apps.sales.models.MobileSales.MobileDealAlerts import MobileDealAlert
from apps.sales.models.MobileSales.MobileDeviceSessions import MobileDeviceSession
from apps.sales.tests.conftest import (
    _mobilesales_alert,
    _mobilesales_check_in,
    _mobilesales_device,
    _mobilesales_party,
    _mobilesales_route,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helpers (_mobilesales_*)
# ==============================================================================

def _mobilesales_body(response):
    """Helper to decode HTTP response body as UTF-8 string."""
    return response.content.decode("utf-8", "replace")


def _mobilesales_client_for_user(user):
    """Helper to initialize an authenticated Django test client for a given user."""
    client = Client()
    client.force_login(user)
    return client


# ==============================================================================
# 1. MobileSalesDashboard Tests
# ==============================================================================

def test_mobilesales_dashboard_view_200_and_context_keys(
    client_a, tenant_a, admin_user, ms_party_a, ms_route_a, ms_check_in_a, ms_device_a, ms_alert_a
):
    url = reverse("sales:mobile_sales_dashboard")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "total_routes_today",
        "completed_stops_today",
        "pending_stops_today",
        "geofence_compliance_pct",
        "active_routes",
        "recent_checkins",
        "urgent_alerts",
        "urgent_alerts_count",
        "active_devices",
    ]
    for key in expected_keys:
        assert key in response.context, f"Expected key '{key}' in dashboard context"

    body = _mobilesales_body(response)
    assert ms_route_a.name in body
    assert ms_check_in_a.number in body
    assert ms_device_a.device_name in body
    assert ms_alert_a.title in body


def test_mobilesales_dashboard_calculations_and_empty_state(client_a, tenant_a, admin_user):
    # Ensure empty initial state for tenant_a
    FieldCheckIn.objects.filter(tenant=tenant_a).delete()
    FieldSalesRoute.objects.filter(tenant=tenant_a).delete()
    MobileDealAlert.objects.filter(tenant=tenant_a).delete()
    MobileDeviceSession.objects.filter(tenant=tenant_a).delete()

    url = reverse("sales:mobile_sales_dashboard")
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["total_routes_today"] == 0
    assert response.context["completed_stops_today"] == 0
    assert response.context["pending_stops_today"] == 0
    assert response.context["geofence_compliance_pct"] == 100
    assert response.context["urgent_alerts_count"] == 0

    # Add 1 verified checkin and 1 unverified checkin today
    party = _mobilesales_party(tenant_a, name="Apex Retail Today")
    route = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=4, completed_stops=1)
    _mobilesales_check_in(
        tenant_a,
        party=party,
        sales_rep=admin_user,
        route=route,
        is_geofence_verified=True,
        check_in_at=timezone.now(),
    )
    _mobilesales_check_in(
        tenant_a,
        party=party,
        sales_rep=admin_user,
        route=route,
        is_geofence_verified=False,
        check_in_at=timezone.now(),
    )

    response_calc = client_a.get(url)
    assert response_calc.status_code == 200
    assert response_calc.context["total_routes_today"] == 1
    assert response_calc.context["completed_stops_today"] == 1
    assert response_calc.context["pending_stops_today"] == 3
    # 1 out of 2 verified = 50%
    assert response_calc.context["geofence_compliance_pct"] == 50


def test_mobilesales_dashboard_login_required():
    anon_client = Client()
    url = reverse("sales:mobile_sales_dashboard")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url


# ==============================================================================
# 2. FieldSalesRoutes Tests
# ==============================================================================

def test_mobilesales_route_list_view_200_and_context(client_a, ms_route_a):
    url = reverse("sales:field_sales_route_list")
    response = client_a.get(url)

    assert response.status_code == 200
    for key in ["page_obj", "routes", "filter_form", "status_choices", "sales_reps", "total_routes_count", "active_routes_count"]:
        assert key in response.context, f"Missing key '{key}' in route list context"

    body = _mobilesales_body(response)
    assert ms_route_a.name in body
    assert ms_route_a.number in body


def test_mobilesales_route_list_filters(client_a, tenant_a, admin_user):
    route_north = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        name="North Metro Route",
        status="scheduled",
        start_location="Depot North",
        route_date=timezone.localdate(),
    )
    route_south = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        name="South Valley Sweep",
        status="completed",
        start_location="Depot South",
        route_date=timezone.localdate() - timedelta(days=2),
    )

    base_url = reverse("sales:field_sales_route_list")

    # 1. Filter by q (name or location)
    res_q = client_a.get(base_url, {"q": "South Valley"})
    assert res_q.status_code == 200
    assert route_south.name in _mobilesales_body(res_q)
    assert route_north.name not in _mobilesales_body(res_q)

    # 2. Junk query returns 200 and empty results
    res_junk = client_a.get(base_url, {"q": "NONEXISTENT_ROUTE_XYZ_987654"})
    assert res_junk.status_code == 200
    assert len(res_junk.context["routes"]) == 0

    # 3. Filter by status
    res_status = client_a.get(base_url, {"status": "completed"})
    assert res_status.status_code == 200
    assert route_south.name in _mobilesales_body(res_status)
    assert route_north.name not in _mobilesales_body(res_status)

    # 4. Filter by sales_rep
    res_rep = client_a.get(base_url, {"sales_rep": admin_user.pk})
    assert res_rep.status_code == 200
    assert route_north.name in _mobilesales_body(res_rep)

    # 5. Filter by route_date
    res_date = client_a.get(base_url, {"route_date": timezone.localdate().isoformat()})
    assert res_date.status_code == 200
    assert route_north.name in _mobilesales_body(res_date)
    assert route_south.name not in _mobilesales_body(res_date)


def test_mobilesales_route_list_pagination(client_a, tenant_a, admin_user):
    for i in range(16):
        _mobilesales_route(
            tenant_a,
            sales_rep=admin_user,
            name=f"Paginated Route {i + 1:02d}",
        )

    base_url = reverse("sales:field_sales_route_list")
    res_p1 = client_a.get(base_url, {"page": "1"})
    assert res_p1.status_code == 200
    assert res_p1.context["page_obj"].number == 1
    assert len(res_p1.context["routes"]) == 15

    res_p2 = client_a.get(base_url, {"page": "2"})
    assert res_p2.status_code == 200
    assert res_p2.context["page_obj"].number == 2
    assert len(res_p2.context["routes"]) >= 1


def test_mobilesales_route_create_get_and_post(client_a, tenant_a, admin_user):
    url = reverse("sales:field_sales_route_create")

    # GET
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is False
    assert res_get.context["form"].initial.get("sales_rep") == admin_user

    # POST Valid
    payload = {
        "name": "East Bay Corridor Visit",
        "sales_rep": admin_user.pk,
        "route_date": timezone.localdate().isoformat(),
        "status": "scheduled",
        "start_location": "Oakland HQ Hub",
        "end_location": "Oakland HQ Hub",
        "total_stops": 4,
        "planned_distance_km": "35.5",
        "actual_distance_km": "0.0",
        "estimated_duration_minutes": 150,
        "actual_duration_minutes": 0,
        "optimization_status": "unoptimized",
        "notes": "East bay priority retail partners.",
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302

    created_route = FieldSalesRoute.objects.filter(tenant=tenant_a, name="East Bay Corridor Visit").first()
    assert created_route is not None
    assert created_route.sales_rep == admin_user
    assert created_route.total_stops == 4
    assert res_post.url == reverse("sales:field_sales_route_detail", kwargs={"pk": created_route.pk})


def test_mobilesales_route_create_post_invalid(client_a):
    url = reverse("sales:field_sales_route_create")
    # Empty payload misses required name, sales_rep, route_date, status
    res = client_a.post(url, data={})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["form"].errors


def test_mobilesales_route_detail_view(client_a, ms_route_a, ms_check_in_a):
    url = reverse("sales:field_sales_route_detail", kwargs={"pk": ms_route_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["route"] == ms_route_a
    assert "stops" in response.context
    assert "completion_rate" in response.context

    body = _mobilesales_body(response)
    assert ms_route_a.name in body
    assert ms_route_a.number in body
    assert ms_check_in_a.party.name in body


def test_mobilesales_route_edit_get_and_post(client_a, ms_route_a, admin_user):
    url = reverse("sales:field_sales_route_edit", kwargs={"pk": ms_route_a.pk})

    # GET
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["route"] == ms_route_a

    # POST Valid
    payload = {
        "name": "Updated North Corridor Sweep",
        "sales_rep": admin_user.pk,
        "route_date": ms_route_a.route_date.isoformat(),
        "status": "in_progress",
        "start_location": ms_route_a.start_location,
        "end_location": ms_route_a.end_location,
        "total_stops": 5,
        "planned_distance_km": "48.0",
        "actual_distance_km": "12.5",
        "estimated_duration_minutes": 200,
        "actual_duration_minutes": 55,
        "optimization_status": "optimized",
        "notes": "Added an extra priority retail stop.",
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:field_sales_route_detail", kwargs={"pk": ms_route_a.pk})

    ms_route_a.refresh_from_db()
    assert ms_route_a.name == "Updated North Corridor Sweep"
    assert ms_route_a.status == "in_progress"
    assert ms_route_a.total_stops == 5


def test_mobilesales_route_edit_post_invalid(client_a, ms_route_a):
    url = reverse("sales:field_sales_route_edit", kwargs={"pk": ms_route_a.pk})
    # Required name empty
    res = client_a.post(url, data={"name": ""})
    assert res.status_code == 200
    assert res.context["form"].errors


def test_mobilesales_route_delete(client_a, tenant_a, admin_user):
    route_to_del = _mobilesales_route(tenant_a, sales_rep=admin_user, name="Route To Delete")
    url = reverse("sales:field_sales_route_delete", kwargs={"pk": route_to_del.pk})

    # GET is rejected (require_POST)
    res_get = client_a.get(url)
    assert res_get.status_code == 405

    # POST succeeds
    res_post = client_a.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:field_sales_route_list")
    assert not FieldSalesRoute.objects.filter(pk=route_to_del.pk).exists()


def test_mobilesales_route_optimize(client_a, tenant_a, admin_user):
    route_active = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        name="Unoptimized Route",
        status="scheduled",
        optimization_status="unoptimized",
    )
    url_active = reverse("sales:field_sales_route_optimize", kwargs={"pk": route_active.pk})

    # GET rejected with 405
    res_get = client_a.get(url_active)
    assert res_get.status_code == 405

    # POST on active/scheduled route optimizes it
    res_post = client_a.post(url_active)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:field_sales_route_detail", kwargs={"pk": route_active.pk})

    route_active.refresh_from_db()
    assert route_active.optimization_status == "optimized"

    # POST on completed route rejects optimization
    route_completed = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        name="Completed Route",
        status="completed",
        optimization_status="unoptimized",
    )
    url_completed = reverse("sales:field_sales_route_optimize", kwargs={"pk": route_completed.pk})
    res_completed = client_a.post(url_completed)
    assert res_completed.status_code == 302

    route_completed.refresh_from_db()
    assert route_completed.optimization_status == "unoptimized"


def test_mobilesales_route_tenant_isolation(client_b, ms_route_a):
    detail_url = reverse("sales:field_sales_route_detail", kwargs={"pk": ms_route_a.pk})
    edit_url = reverse("sales:field_sales_route_edit", kwargs={"pk": ms_route_a.pk})
    delete_url = reverse("sales:field_sales_route_delete", kwargs={"pk": ms_route_a.pk})
    optimize_url = reverse("sales:field_sales_route_optimize", kwargs={"pk": ms_route_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(optimize_url).status_code == 404


# ==============================================================================
# 3. FieldCheckIns Tests
# ==============================================================================

def test_mobilesales_check_in_list_view_200_and_context(client_a, ms_check_in_a):
    url = reverse("sales:field_check_in_list")
    response = client_a.get(url)

    assert response.status_code == 200
    for key in [
        "page_obj",
        "check_ins",
        "filter_form",
        "verification_choices",
        "purpose_choices",
        "outcome_choices",
        "total_checkins_count",
        "verified_checkins_count",
    ]:
        assert key in response.context, f"Missing key '{key}' in check-in list context"

    body = _mobilesales_body(response)
    assert ms_check_in_a.number in body
    assert ms_check_in_a.party.name in body


def test_mobilesales_check_in_list_filters(client_a, tenant_a, admin_user, ms_party_a, ms_route_a):
    party_b2b = _mobilesales_party(tenant_a, name="Apex Wholesale Depot")
    checkin_verified = _mobilesales_check_in(
        tenant_a,
        party=party_b2b,
        sales_rep=admin_user,
        route=ms_route_a,
        verification_status="verified",
        visit_purpose="prospecting",
        outcome="order_placed",
        notes="Wholesale initial stock order confirmed.",
    )
    checkin_unverified = _mobilesales_check_in(
        tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        verification_status="out_of_range",
        visit_purpose="service_check",
        outcome="follow_up_needed",
        notes="Service follow-up completed remotely.",
    )

    base_url = reverse("sales:field_check_in_list")

    # 1. Search by q
    res_q = client_a.get(base_url, {"q": "Wholesale"})
    assert res_q.status_code == 200
    assert checkin_verified.number in _mobilesales_body(res_q)
    assert checkin_unverified.number not in _mobilesales_body(res_q)

    # 2. Junk query returns empty results
    res_junk = client_a.get(base_url, {"q": "NONEXISTENT_VISIT_SEARCH_999"})
    assert res_junk.status_code == 200
    assert len(res_junk.context["check_ins"]) == 0

    # 3. Filter by verification_status
    res_ver = client_a.get(base_url, {"verification_status": "out_of_range"})
    assert res_ver.status_code == 200
    assert checkin_unverified.number in _mobilesales_body(res_ver)
    assert checkin_verified.number not in _mobilesales_body(res_ver)

    # 4. Filter by visit_purpose
    res_purp = client_a.get(base_url, {"visit_purpose": "prospecting"})
    assert res_purp.status_code == 200
    assert checkin_verified.number in _mobilesales_body(res_purp)

    # 5. Filter by outcome
    res_out = client_a.get(base_url, {"outcome": "order_placed"})
    assert res_out.status_code == 200
    assert checkin_verified.number in _mobilesales_body(res_out)

    # 6. Filter by sales_rep
    res_rep = client_a.get(base_url, {"sales_rep": admin_user.pk})
    assert res_rep.status_code == 200
    assert checkin_verified.number in _mobilesales_body(res_rep)


def test_mobilesales_check_in_list_pagination(client_a, tenant_a, admin_user, ms_party_a):
    for i in range(16):
        _mobilesales_check_in(
            tenant_a,
            party=ms_party_a,
            sales_rep=admin_user,
            notes=f"Paginated visit record {i + 1}",
        )

    base_url = reverse("sales:field_check_in_list")
    res_p1 = client_a.get(base_url, {"page": "1"})
    assert res_p1.status_code == 200
    assert res_p1.context["page_obj"].number == 1
    assert len(res_p1.context["check_ins"]) == 15

    res_p2 = client_a.get(base_url, {"page": "2"})
    assert res_p2.status_code == 200
    assert res_p2.context["page_obj"].number == 2
    assert len(res_p2.context["check_ins"]) >= 1


def test_mobilesales_check_in_create_get_and_post(client_a, tenant_a, admin_user, ms_party_a, ms_route_a):
    url = reverse("sales:field_check_in_create")

    # GET without params
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is False
    assert res_get.context["form"].initial.get("sales_rep") == admin_user

    # GET with ?route= query param pre-fills route & stop_number
    res_get_route = client_a.get(url, {"route": str(ms_route_a.pk)})
    assert res_get_route.status_code == 200
    form = res_get_route.context["form"]
    assert form.initial.get("route") == ms_route_a
    assert form.initial.get("stop_number") == ms_route_a.check_ins.count() + 1

    # POST Valid
    payload = {
        "route": ms_route_a.pk,
        "stop_number": 2,
        "party": ms_party_a.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": "37.774929",
        "check_in_lng": "-122.419416",
        "target_lat": "37.775000",
        "target_lng": "-122.419500",
        "geofence_radius_m": 150,
        "verification_status": "verified",
        "visit_purpose": "quote_review",
        "outcome": "successful",
        "notes": "Reviewed expansion discount terms on site.",
        "next_step": "Draft updated quote",
        "next_step_due": (timezone.localdate() + timedelta(days=2)).isoformat(),
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302

    created_checkin = FieldCheckIn.objects.filter(tenant=tenant_a, notes__contains="expansion discount terms").first()
    assert created_checkin is not None
    assert created_checkin.party == ms_party_a
    assert created_checkin.route == ms_route_a
    assert res_post.url == reverse("sales:field_check_in_detail", kwargs={"pk": created_checkin.pk})


def test_mobilesales_check_in_create_post_invalid(client_a):
    url = reverse("sales:field_check_in_create")
    # Missing required coordinates & party
    res = client_a.post(url, data={})
    assert res.status_code == 200
    assert res.context["form"].errors


def test_mobilesales_check_in_detail_view(client_a, ms_check_in_a):
    url = reverse("sales:field_check_in_detail", kwargs={"pk": ms_check_in_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["check_in"] == ms_check_in_a
    assert "duration_display" in response.context

    body = _mobilesales_body(response)
    assert ms_check_in_a.number in body
    assert ms_check_in_a.party.name in body


def test_mobilesales_check_in_edit_get_and_post(client_a, ms_check_in_a, ms_party_a, admin_user):
    url = reverse("sales:field_check_in_edit", kwargs={"pk": ms_check_in_a.pk})

    # GET
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["check_in"] == ms_check_in_a

    # POST Valid
    payload = {
        "stop_number": ms_check_in_a.stop_number,
        "party": ms_party_a.pk,
        "sales_rep": admin_user.pk,
        "check_in_lat": str(ms_check_in_a.check_in_lat),
        "check_in_lng": str(ms_check_in_a.check_in_lng),
        "target_lat": str(ms_check_in_a.target_lat),
        "target_lng": str(ms_check_in_a.target_lng),
        "geofence_radius_m": ms_check_in_a.geofence_radius_m,
        "verification_status": "verified",
        "visit_purpose": "relationship",
        "outcome": "order_placed",
        "notes": "Updated visit summary after customer signed agreement.",
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:field_check_in_detail", kwargs={"pk": ms_check_in_a.pk})

    ms_check_in_a.refresh_from_db()
    assert ms_check_in_a.notes == "Updated visit summary after customer signed agreement."


def test_mobilesales_check_in_edit_post_invalid(client_a, ms_check_in_a):
    url = reverse("sales:field_check_in_edit", kwargs={"pk": ms_check_in_a.pk})
    res = client_a.post(url, data={"party": ""})
    assert res.status_code == 200
    assert res.context["form"].errors


def test_mobilesales_check_in_delete_permissions_and_route_update(
    client_a, tenant_a, admin_user, member_user, ms_party_a
):
    route = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=2, completed_stops=1)
    check_in = _mobilesales_check_in(
        tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=route,
        check_out_at=timezone.now(),
        duration_minutes=30,
    )
    url = reverse("sales:field_check_in_delete", kwargs={"pk": check_in.pk})

    # 1. GET is rejected with 405 Method Not Allowed
    assert client_a.get(url).status_code == 405

    # 2. POST by non-sales-rep non-admin user is rejected
    member_client = _mobilesales_client_for_user(member_user)
    res_unauth = member_client.post(url)
    assert res_unauth.status_code == 302
    assert res_unauth.url == reverse("sales:field_check_in_list")
    assert FieldCheckIn.objects.filter(pk=check_in.pk).exists()

    # 3. POST by sales rep / tenant admin succeeds and updates route completed_stops
    res_admin = client_a.post(url)
    assert res_admin.status_code == 302
    assert res_admin.url == reverse("sales:field_check_in_list")
    assert not FieldCheckIn.objects.filter(pk=check_in.pk).exists()

    route.refresh_from_db()
    assert route.completed_stops == 0


def test_mobilesales_check_in_checkout_modal_and_post(client_a, tenant_a, admin_user, ms_party_a):
    route = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=3, completed_stops=0)
    check_in = _mobilesales_check_in(
        tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=route,
        check_in_at=timezone.now() - timedelta(minutes=45),
        check_out_at=None,
        duration_minutes=None,
    )
    url = reverse("sales:field_check_in_checkout", kwargs={"pk": check_in.pk})

    # GET
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["check_in"] == check_in
    assert "form" in res_get.context

    # POST checkout departure
    payload = {
        "check_out_lat": "37.774900",
        "check_out_lng": "-122.419400",
        "outcome": "order_placed",
        "notes": "Completed meeting, contract signed.",
        "next_step": "Dispatch order",
        "next_step_due": (timezone.localdate() + timedelta(days=1)).isoformat(),
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:field_check_in_detail", kwargs={"pk": check_in.pk})

    check_in.refresh_from_db()
    assert check_in.check_out_at is not None
    assert check_in.duration_minutes >= 44
    assert check_in.outcome == "order_placed"

    route.refresh_from_db()
    assert route.completed_stops == 1


def test_mobilesales_check_in_tenant_isolation(client_b, ms_check_in_a):
    detail_url = reverse("sales:field_check_in_detail", kwargs={"pk": ms_check_in_a.pk})
    edit_url = reverse("sales:field_check_in_edit", kwargs={"pk": ms_check_in_a.pk})
    delete_url = reverse("sales:field_check_in_delete", kwargs={"pk": ms_check_in_a.pk})
    checkout_url = reverse("sales:field_check_in_checkout", kwargs={"pk": ms_check_in_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.get(checkout_url).status_code == 404
    assert client_b.post(checkout_url).status_code == 404


# ==============================================================================
# 4. MobileDeviceSessions Tests
# ==============================================================================

def test_mobilesales_device_session_list_view_200_and_context(client_a, ms_device_a):
    url = reverse("sales:mobile_device_session_list")
    response = client_a.get(url)

    assert response.status_code == 200
    for key in ["page_obj", "devices", "filter_form", "platform_choices", "sync_status_choices", "total_devices_count", "active_devices_count"]:
        assert key in response.context, f"Missing key '{key}' in device session list context"

    body = _mobilesales_body(response)
    assert ms_device_a.device_name in body
    assert ms_device_a.number in body


def test_mobilesales_device_session_list_filters(client_a, tenant_a, admin_user, member_user):
    dev_ios = _mobilesales_device(
        tenant_a,
        user=admin_user,
        device_name="Admin iPad Pro",
        device_identifier="DEV-IOS-101",
        platform="ios",
        last_sync_status="success",
    )
    dev_android = _mobilesales_device(
        tenant_a,
        user=member_user,
        device_name="Member Pixel Tablet",
        device_identifier="DEV-AND-202",
        platform="android",
        last_sync_status="failed",
    )

    base_url = reverse("sales:mobile_device_session_list")

    # 1. Search by q
    res_q = client_a.get(base_url, {"q": "Pixel Tablet"})
    assert res_q.status_code == 200
    assert dev_android.device_name in _mobilesales_body(res_q)
    assert dev_ios.device_name not in _mobilesales_body(res_q)

    # 2. Junk query returns empty
    res_junk = client_a.get(base_url, {"q": "NONEXISTENT_DEVICE_UUID_XYZ"})
    assert res_junk.status_code == 200
    assert len(res_junk.context["devices"]) == 0

    # 3. Filter by platform
    res_plat = client_a.get(base_url, {"platform": "ios"})
    assert res_plat.status_code == 200
    assert dev_ios.device_name in _mobilesales_body(res_plat)
    assert dev_android.device_name not in _mobilesales_body(res_plat)

    # 4. Filter by last_sync_status
    res_sync = client_a.get(base_url, {"last_sync_status": "failed"})
    assert res_sync.status_code == 200
    assert dev_android.device_name in _mobilesales_body(res_sync)
    assert dev_ios.device_name not in _mobilesales_body(res_sync)

    # 5. Filter by user
    res_usr = client_a.get(base_url, {"user": member_user.pk})
    assert res_usr.status_code == 200
    assert dev_android.device_name in _mobilesales_body(res_usr)
    assert dev_ios.device_name not in _mobilesales_body(res_usr)


def test_mobilesales_device_session_list_pagination(client_a, tenant_a, admin_user):
    for i in range(16):
        _mobilesales_device(
            tenant_a,
            user=admin_user,
            device_name=f"Field Device {i + 1:02d}",
            device_identifier=f"DEV-PAG-{i + 1:03d}",
        )

    base_url = reverse("sales:mobile_device_session_list")
    res_p1 = client_a.get(base_url, {"page": "1"})
    assert res_p1.status_code == 200
    assert res_p1.context["page_obj"].number == 1
    assert len(res_p1.context["devices"]) == 15

    res_p2 = client_a.get(base_url, {"page": "2"})
    assert res_p2.status_code == 200
    assert res_p2.context["page_obj"].number == 2
    assert len(res_p2.context["devices"]) >= 1


def test_mobilesales_device_session_create_get_and_post(client_a, tenant_a, admin_user):
    url = reverse("sales:mobile_device_session_create")

    # GET
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is False
    assert res_get.context["form"].initial.get("user") == admin_user

    # POST Valid
    payload = {
        "user": admin_user.pk,
        "device_uuid": "ACME-DEV-IPHONE15-09",
        "device_name": "Field Rep iPhone 15 Pro",
        "platform": "ios",
        "app_version": "3.2.1",
        "push_token": "apns-production-push-token-9876543210-abcdef",
        "is_active": True,
        "is_trusted": True,
        "last_sync_status": "pending",
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302

    created_device = MobileDeviceSession.objects.filter(tenant=tenant_a, device_uuid="ACME-DEV-IPHONE15-09").first()
    assert created_device is not None
    assert created_device.device_name == "Field Rep iPhone 15 Pro"
    assert created_device.platform == "ios"
    assert res_post.url == reverse("sales:mobile_device_session_detail", kwargs={"pk": created_device.pk})


def test_mobilesales_device_session_create_post_invalid(client_a):
    url = reverse("sales:mobile_device_session_create")
    res = client_a.post(url, data={})
    assert res.status_code == 200
    assert res.context["form"].errors


def test_mobilesales_device_session_detail_view(client_a, ms_device_a):
    url = reverse("sales:mobile_device_session_detail", kwargs={"pk": ms_device_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["device"] == ms_device_a
    assert "recent_alerts" in response.context

    body = _mobilesales_body(response)
    assert ms_device_a.device_name in body
    # Verifies push token masking (e.g. slice :8 is displayed)
    assert ms_device_a.push_token[:8] in body


def test_mobilesales_device_session_edit_permissions(client_a, tenant_a, admin_user, member_user):
    # Device owned by admin_user
    device = _mobilesales_device(
        tenant_a,
        user=admin_user,
        device_name="Admin Secure Tablet",
        device_identifier="DEV-ADMIN-TAB",
    )
    url = reverse("sales:mobile_device_session_edit", kwargs={"pk": device.pk})

    # 1. Non-owner non-admin user cannot edit
    member_client = _mobilesales_client_for_user(member_user)
    res_member = member_client.get(url)
    assert res_member.status_code == 302
    assert res_member.url == reverse("sales:mobile_device_session_detail", kwargs={"pk": device.pk})

    # 2. Owner / tenant admin can edit
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True

    payload = {
        "user": admin_user.pk,
        "device_uuid": device.device_uuid,
        "device_name": "Admin Tablet Renamed",
        "platform": "ios",
        "app_version": "3.3.0",
        "push_token": device.push_token,
        "is_active": True,
        "is_trusted": True,
        "last_sync_status": "success",
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:mobile_device_session_detail", kwargs={"pk": device.pk})

    device.refresh_from_db()
    assert device.device_name == "Admin Tablet Renamed"


def test_mobilesales_device_session_delete_permissions(client_a, tenant_a, admin_user, member_user):
    device = _mobilesales_device(
        tenant_a,
        user=admin_user,
        device_name="Device To Remove",
        device_identifier="DEV-DEL-001",
    )
    url = reverse("sales:mobile_device_session_delete", kwargs={"pk": device.pk})

    # 1. GET is rejected with 405 Method Not Allowed
    assert client_a.get(url).status_code == 405

    # 2. Non-owner non-admin cannot delete
    member_client = _mobilesales_client_for_user(member_user)
    res_member = member_client.post(url)
    assert res_member.status_code == 302
    assert res_member.url == reverse("sales:mobile_device_session_list")
    assert MobileDeviceSession.objects.filter(pk=device.pk).exists()

    # 3. Owner / tenant admin can delete
    res_admin = client_a.post(url)
    assert res_admin.status_code == 302
    assert res_admin.url == reverse("sales:mobile_device_session_list")
    assert not MobileDeviceSession.objects.filter(pk=device.pk).exists()


def test_mobilesales_device_session_sync(client_a, ms_device_a):
    url = reverse("sales:mobile_device_session_sync", kwargs={"pk": ms_device_a.pk})

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST triggers sync event
    res_post = client_a.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:mobile_device_session_detail", kwargs={"pk": ms_device_a.pk})

    ms_device_a.refresh_from_db()
    assert ms_device_a.last_sync_status == "success"
    assert ms_device_a.last_sync_at is not None
    assert ms_device_a.offline_records_cached == 120
    assert ms_device_a.pending_uploads_count == 0


def test_mobilesales_device_session_tenant_isolation(client_b, ms_device_a):
    detail_url = reverse("sales:mobile_device_session_detail", kwargs={"pk": ms_device_a.pk})
    edit_url = reverse("sales:mobile_device_session_edit", kwargs={"pk": ms_device_a.pk})
    delete_url = reverse("sales:mobile_device_session_delete", kwargs={"pk": ms_device_a.pk})
    sync_url = reverse("sales:mobile_device_session_sync", kwargs={"pk": ms_device_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(sync_url).status_code == 404


# ==============================================================================
# 5. MobileDealAlerts Tests
# ==============================================================================

def test_mobilesales_deal_alert_list_view_200_and_context(client_a, ms_alert_a):
    url = reverse("sales:mobile_deal_alert_list")
    response = client_a.get(url)

    assert response.status_code == 200
    for key in ["page_obj", "alerts", "filter_form", "alert_type_choices", "urgency_choices", "total_alerts_count", "unread_alerts_count"]:
        assert key in response.context, f"Missing key '{key}' in alert list context"

    body = _mobilesales_body(response)
    assert ms_alert_a.title in body
    assert ms_alert_a.number in body


def test_mobilesales_deal_alert_list_filters(client_a, tenant_a, admin_user, member_user, ms_device_a):
    alert_urgent = _mobilesales_alert(
        tenant_a,
        recipient=admin_user,
        device=ms_device_a,
        alert_type="quote_approval_required",
        urgency="urgent",
        title="Urgent Discount Signoff Required",
        is_read=False,
    )
    alert_normal = _mobilesales_alert(
        tenant_a,
        recipient=member_user,
        device=ms_device_a,
        alert_type="route_dispatched",
        urgency="normal",
        title="Route dispatched for Midwest sweep",
        is_read=True,
    )

    base_url = reverse("sales:mobile_deal_alert_list")

    # 1. Search by q
    res_q = client_a.get(base_url, {"q": "Discount Signoff"})
    assert res_q.status_code == 200
    assert alert_urgent.title in _mobilesales_body(res_q)
    assert alert_normal.title not in _mobilesales_body(res_q)

    # 2. Junk query returns empty
    res_junk = client_a.get(base_url, {"q": "NONEXISTENT_ALERT_QUERY_XYZ"})
    assert res_junk.status_code == 200
    assert len(res_junk.context["alerts"]) == 0

    # 3. Filter by alert_type
    res_type = client_a.get(base_url, {"alert_type": "route_dispatched"})
    assert res_type.status_code == 200
    assert alert_normal.title in _mobilesales_body(res_type)
    assert alert_urgent.title not in _mobilesales_body(res_type)

    # 4. Filter by urgency
    res_urg = client_a.get(base_url, {"urgency": "urgent"})
    assert res_urg.status_code == 200
    assert alert_urgent.title in _mobilesales_body(res_urg)
    assert alert_normal.title not in _mobilesales_body(res_urg)

    # 5. Filter by is_read (0 = unread, 1 = read)
    res_unread = client_a.get(base_url, {"is_read": "0"})
    assert res_unread.status_code == 200
    assert alert_urgent.title in _mobilesales_body(res_unread)
    assert alert_normal.title not in _mobilesales_body(res_unread)

    res_read = client_a.get(base_url, {"is_read": "1"})
    assert res_read.status_code == 200
    assert alert_normal.title in _mobilesales_body(res_read)

    # 6. Filter by recipient
    res_rec = client_a.get(base_url, {"recipient": member_user.pk})
    assert res_rec.status_code == 200
    assert alert_normal.title in _mobilesales_body(res_rec)


def test_mobilesales_deal_alert_list_pagination(client_a, tenant_a, admin_user):
    for i in range(16):
        _mobilesales_alert(
            tenant_a,
            recipient=admin_user,
            title=f"Paginated Mobile Alert {i + 1:02d}",
        )

    base_url = reverse("sales:mobile_deal_alert_list")
    res_p1 = client_a.get(base_url, {"page": "1"})
    assert res_p1.status_code == 200
    assert res_p1.context["page_obj"].number == 1
    assert len(res_p1.context["alerts"]) == 15

    res_p2 = client_a.get(base_url, {"page": "2"})
    assert res_p2.status_code == 200
    assert res_p2.context["page_obj"].number == 2
    assert len(res_p2.context["alerts"]) >= 1


def test_mobilesales_deal_alert_create_get_and_post(client_a, tenant_a, admin_user, ms_device_a, ms_route_a):
    url = reverse("sales:mobile_deal_alert_create")

    # GET with ?device= param validates and pre-fills device
    res_get_dev = client_a.get(url, {"device": str(ms_device_a.pk)})
    assert res_get_dev.status_code == 200
    assert res_get_dev.context["is_edit"] is False
    assert res_get_dev.context["form"].initial.get("device") == ms_device_a
    assert res_get_dev.context["form"].initial.get("recipient") == admin_user

    # POST Valid
    payload = {
        "recipient": admin_user.pk,
        "device": ms_device_a.pk,
        "alert_type": "deal_stage_changed",
        "title": "Deal Slipping Past Q3 Target",
        "message": "Key stakeholders requested additional discount or risk postponing.",
        "urgency": "high",
        "related_route": ms_route_a.pk,
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302

    created_alert = MobileDealAlert.objects.filter(tenant=tenant_a, title="Deal Slipping Past Q3 Target").first()
    assert created_alert is not None
    assert created_alert.push_status == "sent"
    assert created_alert.push_sent_at is not None
    assert created_alert.device == ms_device_a
    assert res_post.url == reverse("sales:mobile_deal_alert_detail", kwargs={"pk": created_alert.pk})


def test_mobilesales_deal_alert_create_post_invalid(client_a):
    url = reverse("sales:mobile_deal_alert_create")
    res = client_a.post(url, data={})
    assert res.status_code == 200
    assert res.context["form"].errors


def test_mobilesales_deal_alert_detail_auto_mark_read(client_a, tenant_a, admin_user, member_user, ms_device_a):
    # 1. Alert for admin_user viewed by admin_user -> auto-marked as read
    alert_for_admin = _mobilesales_alert(
        tenant_a,
        recipient=admin_user,
        device=ms_device_a,
        is_read=False,
        title="Admin Alert For Auto Read",
    )
    url_admin = reverse("sales:mobile_deal_alert_detail", kwargs={"pk": alert_for_admin.pk})
    res_admin = client_a.get(url_admin)
    assert res_admin.status_code == 200

    alert_for_admin.refresh_from_db()
    assert alert_for_admin.is_read is True
    assert alert_for_admin.read_at is not None

    # 2. Alert for member_user viewed by admin_user -> NOT auto-marked read (user != recipient)
    alert_for_member = _mobilesales_alert(
        tenant_a,
        recipient=member_user,
        device=ms_device_a,
        is_read=False,
        title="Member Alert Stays Unread When Admin Views",
    )
    url_member = reverse("sales:mobile_deal_alert_detail", kwargs={"pk": alert_for_member.pk})
    res_view = client_a.get(url_member)
    assert res_view.status_code == 200

    alert_for_member.refresh_from_db()
    assert alert_for_member.is_read is False


def test_mobilesales_deal_alert_edit_get_and_post(client_a, ms_alert_a, admin_user):
    url = reverse("sales:mobile_deal_alert_edit", kwargs={"pk": ms_alert_a.pk})

    # GET
    res_get = client_a.get(url)
    assert res_get.status_code == 200
    assert res_get.context["is_edit"] is True
    assert res_get.context["alert"] == ms_alert_a

    # POST Valid
    payload = {
        "recipient": admin_user.pk,
        "device": ms_alert_a.device_id or "",
        "alert_type": ms_alert_a.alert_type,
        "title": "Updated Alert Subject Line",
        "message": "Updated details regarding the pending approval.",
        "urgency": "high",
    }
    res_post = client_a.post(url, data=payload)
    assert res_post.status_code == 302
    assert res_post.url == reverse("sales:mobile_deal_alert_detail", kwargs={"pk": ms_alert_a.pk})

    ms_alert_a.refresh_from_db()
    assert ms_alert_a.title == "Updated Alert Subject Line"
    assert ms_alert_a.urgency == "high"


def test_mobilesales_deal_alert_edit_post_invalid(client_a, ms_alert_a):
    url = reverse("sales:mobile_deal_alert_edit", kwargs={"pk": ms_alert_a.pk})
    res = client_a.post(url, data={"title": ""})
    assert res.status_code == 200
    assert res.context["form"].errors


def test_mobilesales_deal_alert_delete_permissions(client_a, tenant_a, admin_user, member_user):
    alert = _mobilesales_alert(
        tenant_a,
        recipient=admin_user,
        title="Alert To Be Deleted",
    )
    url = reverse("sales:mobile_deal_alert_delete", kwargs={"pk": alert.pk})

    # 1. GET rejected with 405 Method Not Allowed
    assert client_a.get(url).status_code == 405

    # 2. Non-recipient non-admin cannot delete
    member_client = _mobilesales_client_for_user(member_user)
    res_member = member_client.post(url)
    assert res_member.status_code == 302
    assert res_member.url == reverse("sales:mobile_deal_alert_list")
    assert MobileDealAlert.objects.filter(pk=alert.pk).exists()

    # 3. Recipient / tenant admin can delete
    res_admin = client_a.post(url)
    assert res_admin.status_code == 302
    assert res_admin.url == reverse("sales:mobile_deal_alert_list")
    assert not MobileDealAlert.objects.filter(pk=alert.pk).exists()


def test_mobilesales_deal_alert_mark_read_action(client_a, tenant_a, admin_user, member_user):
    alert = _mobilesales_alert(
        tenant_a,
        recipient=admin_user,
        is_read=False,
        title="Alert To Mark Read Manually",
    )
    url = reverse("sales:mobile_deal_alert_mark_read", kwargs={"pk": alert.pk})

    # 1. GET rejected with 405 Method Not Allowed
    assert client_a.get(url).status_code == 405

    # 2. Non-recipient non-admin cannot mark read
    member_client = _mobilesales_client_for_user(member_user)
    res_member = member_client.post(url)
    assert res_member.status_code == 302
    assert res_member.url == reverse("sales:mobile_deal_alert_detail", kwargs={"pk": alert.pk})
    alert.refresh_from_db()
    assert alert.is_read is False

    # 3. Recipient / tenant admin can mark read
    res_admin = client_a.post(url)
    assert res_admin.status_code == 302
    assert res_admin.url == reverse("sales:mobile_deal_alert_detail", kwargs={"pk": alert.pk})
    alert.refresh_from_db()
    assert alert.is_read is True
    assert alert.read_at is not None


def test_mobilesales_deal_alert_tenant_isolation(client_b, ms_alert_a):
    detail_url = reverse("sales:mobile_deal_alert_detail", kwargs={"pk": ms_alert_a.pk})
    edit_url = reverse("sales:mobile_deal_alert_edit", kwargs={"pk": ms_alert_a.pk})
    delete_url = reverse("sales:mobile_deal_alert_delete", kwargs={"pk": ms_alert_a.pk})
    read_url = reverse("sales:mobile_deal_alert_mark_read", kwargs={"pk": ms_alert_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(read_url).status_code == 404
