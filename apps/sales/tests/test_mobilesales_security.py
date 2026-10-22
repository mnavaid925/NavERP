"""Sub-module 8.16 Mobile Sales & Field Execution — Security & Multi-Tenancy Test Suite.

Covers:
1. Authentication & Anonymous Access:
   - Anonymous access to all 25 mobile sales routes redirects to /accounts/login/
   - Unauthenticated POST requests cannot delete or mutate tenant data
2. Multi-Tenant Isolation (Cross-Tenant IDOR -> 404):
   - Tenant A client requesting Tenant B objects returns 404 across detail, edit, delete, and custom action endpoints:
     - FieldSalesRoute detail, edit (GET/POST), delete (POST), optimize (POST)
     - FieldCheckIn detail, edit (GET/POST), checkout (GET/POST), delete (POST)
     - MobileDeviceSession detail, edit (GET/POST), sync (POST), delete (POST)
     - MobileDealAlert detail, edit (GET/POST), mark_read (POST), delete (POST)
   - Tenant B client requesting Tenant A objects returns 404
   - Tenant A list views never leak Tenant B records
   - Tenant A executive dashboard never aggregates or displays Tenant B metrics/records
3. Cross-Tenant ForeignKey Injection in Forms:
   - Forged POST to route create/edit with foreign sales_rep rejected
   - Forged POST to check-in create/edit with foreign party, route, contact, sales_rep, resulting_quote rejected
   - Forged POST to device session create/edit with foreign user rejected
   - Forged POST to alert create/edit with foreign recipient, device, route, quote rejected
4. Horizontal Authorization & Privilege Gates:
   - Non-recipient non-admin denied deleting or acknowledging someone else's alert (I12)
   - Non-owner non-admin denied editing or deleting someone else's mobile device (I13)
   - Standard user cannot self-certify device as is_trusted (I14)
   - Non-rep non-admin denied deleting GPS visit record (I15)
5. HTTP Method & CSRF Enforcement:
   - State-changing actions reject GET with 405 Method Not Allowed
   - CSRF protection enforced on all mutating POST endpoints (403 Forbidden without CSRF token)
"""
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Currency
from apps.accounts.models import User
from apps.core.models import Party
from apps.sales.models.MobileSales.FieldCheckIns import FieldCheckIn
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute
from apps.sales.models.MobileSales.MobileDealAlerts import MobileDealAlert
from apps.sales.models.MobileSales.MobileDeviceSessions import MobileDeviceSession
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
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

def _mobilesales_quote(tenant, **overrides):
    """Helper to create a CPQQuote for cross-tenant FK injection testing."""
    currency, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={"name": "US Dollar", "symbol": "$"},
    )
    defaults = {
        "tenant": tenant,
        "name": f"{tenant.slug.title()} Deal Quote",
        "currency": currency,
        "status": "draft",
    }
    defaults.update(overrides)
    return CPQQuote.objects.create(**defaults)


def _mobilesales_client_for_user(user, enforce_csrf=False):
    """Helper to create an authenticated test client for a specific user."""
    client = Client(enforce_csrf_checks=enforce_csrf)
    client.force_login(user)
    return client


# ==============================================================================
# 1. Authentication & Anonymous Access Protection
# ==============================================================================

def test_mobilesales_anonymous_access_redirects_to_login(
    ms_route_a, ms_check_in_a, ms_device_a, ms_alert_a
):
    """Anonymous visitors accessing any of the 25 Mobile Sales routes must be redirected to login."""
    anon_client = Client()

    # All 25 Mobile Sales routes (URL name -> args list)
    routes = [
        # Dashboard (1)
        ("mobile_sales_dashboard", []),
        # FieldSalesRoutes (6)
        ("field_sales_route_list", []),
        ("field_sales_route_create", []),
        ("field_sales_route_detail", [ms_route_a.pk]),
        ("field_sales_route_edit", [ms_route_a.pk]),
        ("field_sales_route_delete", [ms_route_a.pk]),
        ("field_sales_route_optimize", [ms_route_a.pk]),
        # FieldCheckIns (6)
        ("field_check_in_list", []),
        ("field_check_in_create", []),
        ("field_check_in_detail", [ms_check_in_a.pk]),
        ("field_check_in_edit", [ms_check_in_a.pk]),
        ("field_check_in_delete", [ms_check_in_a.pk]),
        ("field_check_in_checkout", [ms_check_in_a.pk]),
        # MobileDeviceSessions (6)
        ("mobile_device_session_list", []),
        ("mobile_device_session_create", []),
        ("mobile_device_session_detail", [ms_device_a.pk]),
        ("mobile_device_session_edit", [ms_device_a.pk]),
        ("mobile_device_session_delete", [ms_device_a.pk]),
        ("mobile_device_session_sync", [ms_device_a.pk]),
        # MobileDealAlerts (6)
        ("mobile_deal_alert_list", []),
        ("mobile_deal_alert_create", []),
        ("mobile_deal_alert_detail", [ms_alert_a.pk]),
        ("mobile_deal_alert_edit", [ms_alert_a.pk]),
        ("mobile_deal_alert_delete", [ms_alert_a.pk]),
        ("mobile_deal_alert_mark_read", [ms_alert_a.pk]),
    ]

    for url_name, args in routes:
        url = reverse(f"sales:{url_name}", args=args)
        # Test GET request
        resp_get = anon_client.get(url)
        assert resp_get.status_code == 302, (
            f"Anonymous GET {url_name} returned {resp_get.status_code}, expected 302 redirect."
        )
        assert "/accounts/login/" in resp_get.url or "/login/" in resp_get.url, (
            f"Anonymous GET {url_name} did not redirect to login page (url={resp_get.url})."
        )

        # Test POST request
        resp_post = anon_client.post(url, {})
        assert resp_post.status_code == 302, (
            f"Anonymous POST {url_name} returned {resp_post.status_code}, expected 302 redirect."
        )
        assert "/accounts/login/" in resp_post.url or "/login/" in resp_post.url, (
            f"Anonymous POST {url_name} did not redirect to login page (url={resp_post.url})."
        )

    # Ensure unauthenticated POSTs did not delete or modify any records
    assert FieldSalesRoute.objects.filter(pk=ms_route_a.pk).exists()
    assert FieldCheckIn.objects.filter(pk=ms_check_in_a.pk).exists()
    assert MobileDeviceSession.objects.filter(pk=ms_device_a.pk).exists()
    assert MobileDealAlert.objects.filter(pk=ms_alert_a.pk).exists()


# ==============================================================================
# 2. Multi-Tenant Isolation (Cross-Tenant IDOR -> 404)
# ==============================================================================

def test_mobilesales_cross_tenant_idor_routes_return_404(
    client_a, client_b, ms_route_a, ms_route_b
):
    """FieldSalesRoute IDOR: Tenant A cannot view, edit, delete, or optimize Tenant B routes, and vice versa."""
    # Tenant A -> Tenant B route
    assert client_a.get(reverse("sales:field_sales_route_detail", args=[ms_route_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:field_sales_route_edit", args=[ms_route_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:field_sales_route_edit", args=[ms_route_b.pk]), {"name": "Hacked Route"}).status_code == 404
    assert client_a.post(reverse("sales:field_sales_route_delete", args=[ms_route_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:field_sales_route_optimize", args=[ms_route_b.pk])).status_code == 404

    # Tenant B -> Tenant A route
    assert client_b.get(reverse("sales:field_sales_route_detail", args=[ms_route_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:field_sales_route_edit", args=[ms_route_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:field_sales_route_edit", args=[ms_route_a.pk]), {"name": "Hacked Route"}).status_code == 404
    assert client_b.post(reverse("sales:field_sales_route_delete", args=[ms_route_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:field_sales_route_optimize", args=[ms_route_a.pk])).status_code == 404

    # Verify records remain intact in DB
    ms_route_a.refresh_from_db()
    ms_route_b.refresh_from_db()
    assert FieldSalesRoute.objects.filter(pk=ms_route_a.pk).exists()
    assert FieldSalesRoute.objects.filter(pk=ms_route_b.pk).exists()


def test_mobilesales_cross_tenant_idor_check_ins_return_404(
    client_a, client_b, ms_check_in_a, ms_check_in_b
):
    """FieldCheckIn IDOR: Tenant A cannot view, edit, checkout, or delete Tenant B check-ins, and vice versa."""
    # Tenant A -> Tenant B check-in
    assert client_a.get(reverse("sales:field_check_in_detail", args=[ms_check_in_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:field_check_in_edit", args=[ms_check_in_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:field_check_in_edit", args=[ms_check_in_b.pk]), {"notes": "Tampered"}).status_code == 404
    assert client_a.get(reverse("sales:field_check_in_checkout", args=[ms_check_in_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:field_check_in_checkout", args=[ms_check_in_b.pk]), {}).status_code == 404
    assert client_a.post(reverse("sales:field_check_in_delete", args=[ms_check_in_b.pk])).status_code == 404

    # Tenant B -> Tenant A check-in
    assert client_b.get(reverse("sales:field_check_in_detail", args=[ms_check_in_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:field_check_in_edit", args=[ms_check_in_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:field_check_in_edit", args=[ms_check_in_a.pk]), {"notes": "Tampered"}).status_code == 404
    assert client_b.get(reverse("sales:field_check_in_checkout", args=[ms_check_in_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:field_check_in_checkout", args=[ms_check_in_a.pk]), {}).status_code == 404
    assert client_b.post(reverse("sales:field_check_in_delete", args=[ms_check_in_a.pk])).status_code == 404

    # Verify records remain intact in DB
    assert FieldCheckIn.objects.filter(pk=ms_check_in_a.pk).exists()
    assert FieldCheckIn.objects.filter(pk=ms_check_in_b.pk).exists()


def test_mobilesales_cross_tenant_idor_device_sessions_return_404(
    client_a, client_b, ms_device_a, ms_device_b
):
    """MobileDeviceSession IDOR: Tenant A cannot view, edit, sync, or delete Tenant B devices, and vice versa."""
    # Tenant A -> Tenant B device
    assert client_a.get(reverse("sales:mobile_device_session_detail", args=[ms_device_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:mobile_device_session_edit", args=[ms_device_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:mobile_device_session_edit", args=[ms_device_b.pk]), {"device_name": "Tampered"}).status_code == 404
    assert client_a.post(reverse("sales:mobile_device_session_sync", args=[ms_device_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:mobile_device_session_delete", args=[ms_device_b.pk])).status_code == 404

    # Tenant B -> Tenant A device
    assert client_b.get(reverse("sales:mobile_device_session_detail", args=[ms_device_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:mobile_device_session_edit", args=[ms_device_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:mobile_device_session_edit", args=[ms_device_a.pk]), {"device_name": "Tampered"}).status_code == 404
    assert client_b.post(reverse("sales:mobile_device_session_sync", args=[ms_device_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:mobile_device_session_delete", args=[ms_device_a.pk])).status_code == 404

    # Verify records remain intact in DB
    assert MobileDeviceSession.objects.filter(pk=ms_device_a.pk).exists()
    assert MobileDeviceSession.objects.filter(pk=ms_device_b.pk).exists()


def test_mobilesales_cross_tenant_idor_deal_alerts_return_404(
    client_a, client_b, ms_alert_a, ms_alert_b
):
    """MobileDealAlert IDOR: Tenant A cannot view, edit, mark read, or delete Tenant B alerts, and vice versa."""
    # Tenant A -> Tenant B alert
    assert client_a.get(reverse("sales:mobile_deal_alert_detail", args=[ms_alert_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:mobile_deal_alert_edit", args=[ms_alert_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:mobile_deal_alert_edit", args=[ms_alert_b.pk]), {"title": "Tampered"}).status_code == 404
    assert client_a.post(reverse("sales:mobile_deal_alert_mark_read", args=[ms_alert_b.pk])).status_code == 404
    assert client_a.post(reverse("sales:mobile_deal_alert_delete", args=[ms_alert_b.pk])).status_code == 404

    # Tenant B -> Tenant A alert
    assert client_b.get(reverse("sales:mobile_deal_alert_detail", args=[ms_alert_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:mobile_deal_alert_edit", args=[ms_alert_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:mobile_deal_alert_edit", args=[ms_alert_a.pk]), {"title": "Tampered"}).status_code == 404
    assert client_b.post(reverse("sales:mobile_deal_alert_mark_read", args=[ms_alert_a.pk])).status_code == 404
    assert client_b.post(reverse("sales:mobile_deal_alert_delete", args=[ms_alert_a.pk])).status_code == 404

    # Verify records remain intact in DB and alert_b remains unread
    ms_alert_b.refresh_from_db()
    assert MobileDealAlert.objects.filter(pk=ms_alert_a.pk).exists()
    assert MobileDealAlert.objects.filter(pk=ms_alert_b.pk).exists()
    assert ms_alert_b.is_read is False


def test_mobilesales_cross_tenant_list_views_never_leak_records(
    client_a, client_b, ms_route_a, ms_route_b,
    ms_check_in_a, ms_check_in_b,
    ms_device_a, ms_device_b,
    ms_alert_a, ms_alert_b
):
    """List views strictly partition records by tenant; Tenant B records never leak to Tenant A."""
    # 1. Routes List
    resp_a = client_a.get(reverse("sales:field_sales_route_list"))
    assert ms_route_a in resp_a.context["routes"]
    assert ms_route_b not in resp_a.context["routes"]

    resp_b = client_b.get(reverse("sales:field_sales_route_list"))
    assert ms_route_b in resp_b.context["routes"]
    assert ms_route_a not in resp_b.context["routes"]

    # 2. Check-Ins List
    resp_a = client_a.get(reverse("sales:field_check_in_list"))
    assert ms_check_in_a in resp_a.context["check_ins"]
    assert ms_check_in_b not in resp_a.context["check_ins"]

    resp_b = client_b.get(reverse("sales:field_check_in_list"))
    assert ms_check_in_b in resp_b.context["check_ins"]
    assert ms_check_in_a not in resp_b.context["check_ins"]

    # 3. Device Sessions List
    resp_a = client_a.get(reverse("sales:mobile_device_session_list"))
    assert ms_device_a in resp_a.context["devices"]
    assert ms_device_b not in resp_a.context["devices"]

    resp_b = client_b.get(reverse("sales:mobile_device_session_list"))
    assert ms_device_b in resp_b.context["devices"]
    assert ms_device_a not in resp_b.context["devices"]

    # 4. Deal Alerts List
    resp_a = client_a.get(reverse("sales:mobile_deal_alert_list"))
    assert ms_alert_a in resp_a.context["alerts"]
    assert ms_alert_b not in resp_a.context["alerts"]

    resp_b = client_b.get(reverse("sales:mobile_deal_alert_list"))
    assert ms_alert_b in resp_b.context["alerts"]
    assert ms_alert_a not in resp_b.context["alerts"]


def test_mobilesales_cross_tenant_dashboard_isolation(
    client_a, client_b, tenant_a, tenant_b, admin_user, admin_b
):
    """Tenant A executive dashboard strictly partitions KPI aggregations and never includes Tenant B records."""
    today = timezone.localdate()

    # Clear prior data for today to start with precise counts
    FieldSalesRoute.objects.filter(route_date=today).delete()

    # Tenant A has 1 route with 4 stops (2 completed)
    route_a = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        name="Acme Alpha Sweep",
        route_date=today,
        total_stops=4,
        completed_stops=2,
    )
    # Tenant B has 2 routes with 10 stops (7 completed)
    route_b1 = _mobilesales_route(
        tenant_b,
        sales_rep=admin_b,
        name="Globex Beta Sweep 1",
        route_date=today,
        total_stops=6,
        completed_stops=5,
    )
    route_b2 = _mobilesales_route(
        tenant_b,
        sales_rep=admin_b,
        name="Globex Beta Sweep 2",
        route_date=today,
        total_stops=4,
        completed_stops=2,
    )

    # Check Tenant A dashboard
    resp_a = client_a.get(reverse("sales:mobile_sales_dashboard"))
    assert resp_a.status_code == 200

    ctx_a = resp_a.context
    # Tenant A must show exactly 1 route today and 4 stops (2 completed, 2 pending)
    assert ctx_a["total_routes_today"] == 1
    assert ctx_a["completed_stops_today"] == 2
    assert ctx_a["pending_stops_today"] == 2

    # Active routes list in Tenant A must only contain Tenant A route
    assert route_a in ctx_a["active_routes"]
    assert route_b1 not in ctx_a["active_routes"]
    assert route_b2 not in ctx_a["active_routes"]

    content_a = resp_a.content.decode("utf-8")
    assert "Globex Beta Sweep" not in content_a

    # Check Tenant B dashboard
    resp_b = client_b.get(reverse("sales:mobile_sales_dashboard"))
    assert resp_b.status_code == 200

    ctx_b = resp_b.context
    # Tenant B must show exactly 2 routes today and 10 stops (7 completed, 3 pending)
    assert ctx_b["total_routes_today"] == 2
    assert ctx_b["completed_stops_today"] == 7
    assert ctx_b["pending_stops_today"] == 3

    assert route_b1 in ctx_b["active_routes"]
    assert route_b2 in ctx_b["active_routes"]
    assert route_a not in ctx_b["active_routes"]


# ==============================================================================
# 3. Cross-Tenant ForeignKey Injection in Forms
# ==============================================================================

def test_mobilesales_fk_injection_route_form_rejects_foreign_sales_rep(
    client_a, tenant_a, admin_b, ms_route_a
):
    """FieldSalesRoute form strictly rejects foreign tenant user as sales_rep on create and edit."""
    # 1. Create Route with Tenant B user as sales_rep
    post_data_create = {
        "name": "Injected Rep Route",
        "sales_rep": admin_b.pk,
        "route_date": str(timezone.localdate()),
        "status": "scheduled",
        "start_location": "Depot 1",
        "end_location": "Depot 1",
        "total_stops": 3,
        "planned_distance_km": "10.0",
        "actual_distance_km": "0.0",
        "estimated_duration_minutes": 60,
        "actual_duration_minutes": 0,
        "optimization_status": "pending",
    }
    resp = client_a.post(reverse("sales:field_sales_route_create"), post_data_create)
    assert resp.status_code == 200  # Re-renders form with validation error
    assert "sales_rep" in resp.context["form"].errors
    assert not FieldSalesRoute.objects.filter(name="Injected Rep Route").exists()

    # 2. Edit Route to inject Tenant B user as sales_rep
    post_data_edit = {
        "name": ms_route_a.name,
        "sales_rep": admin_b.pk,
        "route_date": str(ms_route_a.route_date),
        "status": ms_route_a.status,
        "start_location": ms_route_a.start_location,
        "end_location": ms_route_a.end_location,
        "total_stops": ms_route_a.total_stops,
        "planned_distance_km": str(ms_route_a.planned_distance_km),
        "actual_distance_km": str(ms_route_a.actual_distance_km),
        "estimated_duration_minutes": ms_route_a.estimated_duration_minutes,
        "actual_duration_minutes": ms_route_a.actual_duration_minutes,
        "optimization_status": ms_route_a.optimization_status,
    }
    resp_edit = client_a.post(reverse("sales:field_sales_route_edit", args=[ms_route_a.pk]), post_data_edit)
    assert resp_edit.status_code == 200
    assert "sales_rep" in resp_edit.context["form"].errors

    ms_route_a.refresh_from_db()
    assert ms_route_a.sales_rep != admin_b


def test_mobilesales_fk_injection_check_in_form_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_user, admin_b,
    ms_party_a, ms_party_b, ms_route_a, ms_route_b
):
    """FieldCheckIn form strictly rejects foreign party, route, contact, sales_rep, or quote."""
    quote_b = _mobilesales_quote(tenant_b, name="Globex CPQ Deal")

    base_checkin_data = {
        "stop_number": 1,
        "check_in_lat": "37.774900",
        "check_in_lng": "-122.419400",
        "target_lat": "37.775000",
        "target_lng": "-122.419500",
        "geofence_radius_m": 150,
        "verification_status": "verified",
        "visit_purpose": "relationship",
        "outcome": "order_placed",
        "notes": "Field test notes.",
    }

    # 1. Foreign party injection
    data_foreign_party = {
        **base_checkin_data,
        "party": ms_party_b.pk,
        "route": ms_route_a.pk,
        "sales_rep": admin_user.pk,
    }
    resp = client_a.post(reverse("sales:field_check_in_create"), data_foreign_party)
    assert resp.status_code == 200
    assert "party" in resp.context["form"].errors

    # 2. Foreign route injection
    data_foreign_route = {
        **base_checkin_data,
        "party": ms_party_a.pk,
        "route": ms_route_b.pk,
        "sales_rep": admin_user.pk,
    }
    resp = client_a.post(reverse("sales:field_check_in_create"), data_foreign_route)
    assert resp.status_code == 200
    assert "route" in resp.context["form"].errors

    # 3. Foreign contact party injection
    data_foreign_contact = {
        **base_checkin_data,
        "party": ms_party_a.pk,
        "contact": ms_party_b.pk,
        "sales_rep": admin_user.pk,
    }
    resp = client_a.post(reverse("sales:field_check_in_create"), data_foreign_contact)
    assert resp.status_code == 200
    assert "contact" in resp.context["form"].errors

    # 4. Foreign sales_rep injection
    data_foreign_rep = {
        **base_checkin_data,
        "party": ms_party_a.pk,
        "route": ms_route_a.pk,
        "sales_rep": admin_b.pk,
    }
    resp = client_a.post(reverse("sales:field_check_in_create"), data_foreign_rep)
    assert resp.status_code == 200
    assert "sales_rep" in resp.context["form"].errors

    # 5. Foreign resulting_quote injection
    data_foreign_quote = {
        **base_checkin_data,
        "party": ms_party_a.pk,
        "resulting_quote": quote_b.pk,
        "sales_rep": admin_user.pk,
    }
    resp = client_a.post(reverse("sales:field_check_in_create"), data_foreign_quote)
    assert resp.status_code == 200
    assert "resulting_quote" in resp.context["form"].errors

    # Ensure no check-ins were created with injected foreign references
    assert not FieldCheckIn.objects.filter(notes="Field test notes.").exists()


def test_mobilesales_fk_injection_device_session_form_rejects_foreign_user(
    client_a, admin_b, ms_device_a
):
    """MobileDeviceSession form strictly rejects foreign user as device user."""
    # 1. Device Create with Tenant B user
    post_data_create = {
        "user": admin_b.pk,
        "device_uuid": "INJECTED-DEVICE-UUID-999",
        "device_name": "Injected Foreign iPad",
        "platform": "ios",
        "app_version": "2.4.0",
        "push_token": "token-xyz-123",
        "is_active": True,
        "last_sync_status": "success",
    }
    resp = client_a.post(reverse("sales:mobile_device_session_create"), post_data_create)
    assert resp.status_code == 200
    assert "user" in resp.context["form"].errors
    assert not MobileDeviceSession.objects.filter(device_uuid="INJECTED-DEVICE-UUID-999").exists()

    # 2. Device Edit with Tenant B user
    post_data_edit = {
        "user": admin_b.pk,
        "device_uuid": ms_device_a.device_uuid,
        "device_name": ms_device_a.device_name,
        "platform": ms_device_a.platform,
        "app_version": ms_device_a.app_version,
        "push_token": ms_device_a.push_token,
        "is_active": ms_device_a.is_active,
        "last_sync_status": ms_device_a.last_sync_status,
    }
    resp_edit = client_a.post(reverse("sales:mobile_device_session_edit", args=[ms_device_a.pk]), post_data_edit)
    assert resp_edit.status_code == 200
    assert "user" in resp_edit.context["form"].errors

    ms_device_a.refresh_from_db()
    assert ms_device_a.user != admin_b


def test_mobilesales_fk_injection_deal_alert_form_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_user, admin_b,
    ms_device_a, ms_device_b, ms_route_b
):
    """MobileDealAlert form strictly rejects foreign recipient, device, route, or quote."""
    quote_b = _mobilesales_quote(tenant_b, name="Foreign CPQ Quote")

    base_alert_data = {
        "alert_type": "quote_approval_required",
        "title": "Injected Alert Test",
        "message": "Testing cross tenant injection.",
        "urgency": "urgent",
    }

    # 1. Foreign recipient injection
    data_foreign_recipient = {
        **base_alert_data,
        "recipient": admin_b.pk,
        "device": ms_device_a.pk,
    }
    resp = client_a.post(reverse("sales:mobile_deal_alert_create"), data_foreign_recipient)
    assert resp.status_code == 200
    assert "recipient" in resp.context["form"].errors

    # 2. Foreign device injection
    data_foreign_device = {
        **base_alert_data,
        "recipient": admin_user.pk,
        "device": ms_device_b.pk,
    }
    resp = client_a.post(reverse("sales:mobile_deal_alert_create"), data_foreign_device)
    assert resp.status_code == 200
    assert "device" in resp.context["form"].errors

    # 3. Foreign route injection
    data_foreign_route = {
        **base_alert_data,
        "recipient": admin_user.pk,
        "device": ms_device_a.pk,
        "related_route": ms_route_b.pk,
    }
    resp = client_a.post(reverse("sales:mobile_deal_alert_create"), data_foreign_route)
    assert resp.status_code == 200
    assert "related_route" in resp.context["form"].errors

    # 4. Foreign quote injection
    data_foreign_quote = {
        **base_alert_data,
        "recipient": admin_user.pk,
        "device": ms_device_a.pk,
        "related_quote": quote_b.pk,
    }
    resp = client_a.post(reverse("sales:mobile_deal_alert_create"), data_foreign_quote)
    assert resp.status_code == 200
    assert "related_quote" in resp.context["form"].errors

    # Verify no alert created
    assert not MobileDealAlert.objects.filter(title="Injected Alert Test").exists()


# ==============================================================================
# 4. Horizontal Authorization & Privilege Gates
# ==============================================================================

def test_mobilesales_privilege_non_recipient_non_admin_denied_alert_actions(
    tenant_a, admin_user, member_user, member_client, client_a, ms_device_a
):
    """I12: Non-recipient non-admin denied deleting or acknowledging someone else's alert."""
    # Alert assigned to admin_user
    alert = _mobilesales_alert(
        tenant_a,
        recipient=admin_user,
        device=ms_device_a,
        title="Admin Private Deal Alert",
        is_read=False,
    )

    # 1. Non-recipient standard user attempts to delete someone else's alert -> Denied
    resp_del = member_client.post(reverse("sales:mobile_deal_alert_delete", args=[alert.pk]))
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("sales:mobile_deal_alert_list")
    assert MobileDealAlert.objects.filter(pk=alert.pk).exists()

    # 2. Non-recipient standard user attempts to mark read someone else's alert -> Denied
    resp_read = member_client.post(reverse("sales:mobile_deal_alert_mark_read", args=[alert.pk]))
    assert resp_read.status_code == 302
    assert resp_read.url == reverse("sales:mobile_deal_alert_detail", args=[alert.pk])
    alert.refresh_from_db()
    assert alert.is_read is False

    # 3. Non-recipient standard user viewing detail page does NOT auto-mark it as read
    resp_detail = member_client.get(reverse("sales:mobile_deal_alert_detail", args=[alert.pk]))
    assert resp_detail.status_code == 200
    alert.refresh_from_db()
    assert alert.is_read is False

    # 4. Recipient viewing detail page auto-marks it as read
    resp_admin_detail = client_a.get(reverse("sales:mobile_deal_alert_detail", args=[alert.pk]))
    assert resp_admin_detail.status_code == 200
    alert.refresh_from_db()
    assert alert.is_read is True

    # 5. Alert assigned to member_user: admin (tenant admin) CAN delete it
    member_alert = _mobilesales_alert(
        tenant_a,
        recipient=member_user,
        device=ms_device_a,
        title="Member Deal Alert",
    )
    resp_admin_del = client_a.post(reverse("sales:mobile_deal_alert_delete", args=[member_alert.pk]))
    assert resp_admin_del.status_code == 302
    assert not MobileDealAlert.objects.filter(pk=member_alert.pk).exists()


def test_mobilesales_privilege_non_owner_non_admin_denied_device_edit_delete(
    tenant_a, admin_user, member_user, member_client, client_a
):
    """I13: Non-owner non-admin denied editing or deleting someone else's mobile device."""
    # Device owned by admin_user
    admin_device = _mobilesales_device(
        tenant_a,
        user=admin_user,
        device_name="Admin iPad Pro",
        device_identifier="DEV-ADMIN-IPAD",
    )

    # 1. Non-owner standard user GET edit -> Denied (redirects to detail)
    resp_edit_get = member_client.get(reverse("sales:mobile_device_session_edit", args=[admin_device.pk]))
    assert resp_edit_get.status_code == 302
    assert resp_edit_get.url == reverse("sales:mobile_device_session_detail", args=[admin_device.pk])

    # 2. Non-owner standard user POST edit -> Denied
    resp_edit_post = member_client.post(
        reverse("sales:mobile_device_session_edit", args=[admin_device.pk]),
        {"device_name": "Tampered Admin iPad"},
    )
    assert resp_edit_post.status_code == 302
    assert resp_edit_post.url == reverse("sales:mobile_device_session_detail", args=[admin_device.pk])
    admin_device.refresh_from_db()
    assert admin_device.device_name == "Admin iPad Pro"

    # 3. Non-owner standard user POST delete -> Denied
    resp_del_post = member_client.post(reverse("sales:mobile_device_session_delete", args=[admin_device.pk]))
    assert resp_del_post.status_code == 302
    assert resp_del_post.url == reverse("sales:mobile_device_session_list")
    assert MobileDeviceSession.objects.filter(pk=admin_device.pk).exists()

    # 4. Device owned by member_user: member CAN edit their own device
    member_device = _mobilesales_device(
        tenant_a,
        user=member_user,
        device_name="Member Android Phone",
        device_identifier="DEV-MEMBER-PIXEL",
    )
    resp_member_edit = member_client.post(
        reverse("sales:mobile_device_session_edit", args=[member_device.pk]),
        {
            "user": member_user.pk,
            "device_name": "Member Pixel 8 Pro",
            "device_uuid": member_device.device_uuid,
            "platform": "android",
            "app_version": "2.4.0",
            "push_token": "token-pixel-999",
            "is_active": True,
            "last_sync_status": "success",
        },
    )
    assert resp_member_edit.status_code == 302
    member_device.refresh_from_db()
    assert member_device.device_name == "Member Pixel 8 Pro"

    # 5. Tenant admin CAN edit and delete member_user's device
    resp_admin_delete = client_a.post(reverse("sales:mobile_device_session_delete", args=[member_device.pk]))
    assert resp_admin_delete.status_code == 302
    assert not MobileDeviceSession.objects.filter(pk=member_device.pk).exists()


def test_mobilesales_privilege_standard_user_cannot_self_certify_device_trusted(
    tenant_a, member_user, member_client, client_a
):
    """I14: Standard user cannot self-certify device as is_trusted on create or edit."""
    # 1. Standard user submits is_trusted=True on device creation
    post_data_create = {
        "user": member_user.pk,
        "device_name": "Member Personal iPhone",
        "device_uuid": "MEMBER-IPHONE-15",
        "platform": "ios",
        "app_version": "2.4.0",
        "push_token": "token-iphone-123",
        "is_active": True,
        "is_trusted": True,  # Standard user attempting privilege escalation
        "last_sync_status": "success",
    }
    resp = member_client.post(reverse("sales:mobile_device_session_create"), post_data_create)
    assert resp.status_code == 302
    created_device = MobileDeviceSession.objects.get(device_uuid="MEMBER-IPHONE-15")
    # Device must NOT be trusted because creator is a standard member
    assert created_device.is_trusted is False

    # 2. Standard user attempts to flip is_trusted to True via edit
    post_data_edit = {
        "user": member_user.pk,
        "device_name": "Member Personal iPhone Updated",
        "device_uuid": created_device.device_uuid,
        "platform": created_device.platform,
        "app_version": created_device.app_version,
        "push_token": created_device.push_token,
        "is_active": True,
        "is_trusted": True,  # Escalation attempt
        "last_sync_status": "success",
    }
    resp_edit = member_client.post(
        reverse("sales:mobile_device_session_edit", args=[created_device.pk]), post_data_edit
    )
    assert resp_edit.status_code == 302
    created_device.refresh_from_db()
    assert created_device.is_trusted is False

    # 3. Tenant administrator CAN certify device as is_trusted
    resp_admin_edit = client_a.post(
        reverse("sales:mobile_device_session_edit", args=[created_device.pk]), post_data_edit
    )
    assert resp_admin_edit.status_code == 302
    created_device.refresh_from_db()
    assert created_device.is_trusted is True


def test_mobilesales_privilege_non_rep_non_admin_denied_deleting_visit_record(
    tenant_a, admin_user, member_user, member_client, client_a, ms_party_a, ms_route_a
):
    """I15: Non-rep non-admin denied deleting GPS visit record."""
    # Check-in assigned to admin_user
    check_in_rep_admin = _mobilesales_check_in(
        tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        notes="Admin visit record.",
    )

    # 1. Standard member (who is not the sales_rep) attempts to delete -> Denied
    resp_del = member_client.post(reverse("sales:field_check_in_delete", args=[check_in_rep_admin.pk]))
    assert resp_del.status_code == 302
    assert resp_del.url == reverse("sales:field_check_in_list")
    assert FieldCheckIn.objects.filter(pk=check_in_rep_admin.pk).exists()

    # 2. Check-in assigned to member_user: member CAN delete their own check-in
    check_in_rep_member = _mobilesales_check_in(
        tenant_a,
        party=ms_party_a,
        sales_rep=member_user,
        route=ms_route_a,
        notes="Member visit record.",
    )
    resp_member_del = member_client.post(reverse("sales:field_check_in_delete", args=[check_in_rep_member.pk]))
    assert resp_member_del.status_code == 302
    assert not FieldCheckIn.objects.filter(pk=check_in_rep_member.pk).exists()

    # 3. Tenant admin CAN delete check-in even when sales_rep is someone else
    check_in_for_admin_delete = _mobilesales_check_in(
        tenant_a,
        party=ms_party_a,
        sales_rep=member_user,
        route=ms_route_a,
        notes="Visit to be removed by tenant admin.",
    )
    resp_admin_del = client_a.post(reverse("sales:field_check_in_delete", args=[check_in_for_admin_delete.pk]))
    assert resp_admin_del.status_code == 302
    assert not FieldCheckIn.objects.filter(pk=check_in_for_admin_delete.pk).exists()


# ==============================================================================
# 5. HTTP Method & CSRF Enforcement
# ==============================================================================

def test_mobilesales_http_method_protection_post_only_rejects_get(
    client_a, ms_route_a, ms_check_in_a, ms_device_a, ms_alert_a
):
    """State-changing POST-only endpoints strictly reject GET with 405 Method Not Allowed."""
    post_only_routes = [
        reverse("sales:field_sales_route_delete", args=[ms_route_a.pk]),
        reverse("sales:field_sales_route_optimize", args=[ms_route_a.pk]),
        reverse("sales:field_check_in_delete", args=[ms_check_in_a.pk]),
        reverse("sales:mobile_device_session_delete", args=[ms_device_a.pk]),
        reverse("sales:mobile_device_session_sync", args=[ms_device_a.pk]),
        reverse("sales:mobile_deal_alert_delete", args=[ms_alert_a.pk]),
        reverse("sales:mobile_deal_alert_mark_read", args=[ms_alert_a.pk]),
    ]

    for url in post_only_routes:
        resp = client_a.get(url)
        assert resp.status_code == 405, (
            f"GET request to POST-only endpoint {url} returned {resp.status_code}, expected 405."
        )

    # Ensure none of the entities were deleted or altered
    assert FieldSalesRoute.objects.filter(pk=ms_route_a.pk).exists()
    assert FieldCheckIn.objects.filter(pk=ms_check_in_a.pk).exists()
    assert MobileDeviceSession.objects.filter(pk=ms_device_a.pk).exists()
    assert MobileDealAlert.objects.filter(pk=ms_alert_a.pk).exists()


def test_mobilesales_csrf_enforcement_on_mutating_post_endpoints(
    tenant_a, admin_user, ms_route_a, ms_check_in_a, ms_device_a, ms_alert_a
):
    """CSRF protection is enforced on all 16 mutating POST endpoints (rejects without token with 403)."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    mutating_routes = [
        # FieldSalesRoute endpoints (4)
        reverse("sales:field_sales_route_create"),
        reverse("sales:field_sales_route_edit", args=[ms_route_a.pk]),
        reverse("sales:field_sales_route_delete", args=[ms_route_a.pk]),
        reverse("sales:field_sales_route_optimize", args=[ms_route_a.pk]),
        # FieldCheckIn endpoints (4)
        reverse("sales:field_check_in_create"),
        reverse("sales:field_check_in_edit", args=[ms_check_in_a.pk]),
        reverse("sales:field_check_in_delete", args=[ms_check_in_a.pk]),
        reverse("sales:field_check_in_checkout", args=[ms_check_in_a.pk]),
        # MobileDeviceSession endpoints (4)
        reverse("sales:mobile_device_session_create"),
        reverse("sales:mobile_device_session_edit", args=[ms_device_a.pk]),
        reverse("sales:mobile_device_session_delete", args=[ms_device_a.pk]),
        reverse("sales:mobile_device_session_sync", args=[ms_device_a.pk]),
        # MobileDealAlert endpoints (4)
        reverse("sales:mobile_deal_alert_create"),
        reverse("sales:mobile_deal_alert_edit", args=[ms_alert_a.pk]),
        reverse("sales:mobile_deal_alert_delete", args=[ms_alert_a.pk]),
        reverse("sales:mobile_deal_alert_mark_read", args=[ms_alert_a.pk]),
    ]

    for url in mutating_routes:
        resp = csrf_client.post(url, {"data": "test_csrf"})
        assert resp.status_code == 403, (
            f"POST without CSRF token to {url} returned {resp.status_code}, expected 403 Forbidden."
        )

    # Ensure records were not deleted or modified
    assert FieldSalesRoute.objects.filter(pk=ms_route_a.pk).exists()
    assert FieldCheckIn.objects.filter(pk=ms_check_in_a.pk).exists()
    assert MobileDeviceSession.objects.filter(pk=ms_device_a.pk).exists()
    assert MobileDealAlert.objects.filter(pk=ms_alert_a.pk).exists()
