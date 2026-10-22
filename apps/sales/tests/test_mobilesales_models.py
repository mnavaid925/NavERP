"""Tests for Sales 8.16 Mobile Sales & Field Execution models.

Covers:
1. FieldSalesRoute:
   - Creation, __str__, number generation (FSR-#####)
   - Status choices (draft, scheduled, in_progress, completed, cancelled)
   - Optimization status choices (unoptimized, optimized, manual_order)
   - Validation in clean(): completed_stops > total_stops, planned_distance_km < 0,
     actual_distance_km < 0, estimated_duration < 0, actual_duration < 0, sales_rep tenant isolation
   - Properties: completion_rate_pct, progress_display, generate_navigation_url()
2. FieldCheckIn:
   - Creation, __str__, number generation (CHK-#####)
   - Status & purpose choices: verification_status, visit_purpose, outcome
   - Haversine geofence calculation: calculate_distance() in metres, distance <= radius logic
   - Duration calculation: calculate_duration() in minutes, auto-population in clean()
   - Validation in clean(): lat/lng coordinate range validation (-90..90, -180..180),
     departure time validation, cross-tenant isolation (party, sales_rep, route, contact,
     opportunity, communication_log)
3. MobileDeviceSession:
   - Creation, __str__, number generation (MDS-#####)
   - Platform choices, sync status choices
   - record_sync_event(status, cached_count, pending_count, ip)
   - is_outdated property
   - Cross-tenant user validation in clean()
4. MobileDealAlert:
   - Creation, __str__, number generation (MDA-#####)
   - Alert type choices, urgency choices, push status choices
   - mark_as_read() and dispatch_alert() methods
   - Cross-tenant isolation validation in clean()
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.crm.models import CommunicationLog, Opportunity
from apps.sales.models import (
    FieldCheckIn,
    FieldSalesRoute,
    MobileDealAlert,
    MobileDeviceSession,
    ALERT_TYPE_CHOICES,
    OPTIMIZATION_STATUS_CHOICES,
    PLATFORM_CHOICES,
    PUSH_STATUS_CHOICES,
    ROUTE_STATUS_CHOICES,
    SYNC_STATUS_CHOICES,
    URGENCY_CHOICES,
    VERIFICATION_STATUS_CHOICES,
    VISIT_OUTCOME_CHOICES,
    VISIT_PURPOSE_CHOICES,
)
from apps.sales.tests.conftest import (
    _mobilesales_alert,
    _mobilesales_check_in,
    _mobilesales_device,
    _mobilesales_party,
    _mobilesales_route,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper functions (_mobilesales_*)
# ==============================================================================

def _mobilesales_opportunity(tenant, account=None, name="Field Mobile Deal"):
    if account is None:
        account = _mobilesales_party(tenant, name=f"Account for {name}")
    return Opportunity.objects.create(
        tenant=tenant,
        name=name,
        account=account,
        amount=Decimal("25000.00"),
        stage="prospecting",
        probability=25,
        close_date=timezone.localdate() + timedelta(days=30),
    )


def _mobilesales_communication_log(tenant, owner=None, subject="Field Discussion"):
    return CommunicationLog.objects.create(
        tenant=tenant,
        channel="meeting",
        subject=subject,
        owner=owner,
    )


# ==============================================================================
# FieldSalesRoute Tests
# ==============================================================================

def test_mobilesales_route_creation_and_str(tenant_a, ms_route_a):
    assert ms_route_a.number.startswith("FSR-")
    expected_str = f"{ms_route_a.number} — {ms_route_a.name} ({ms_route_a.route_date})"
    assert str(ms_route_a) == expected_str
    assert ms_route_a.tenant == tenant_a
    assert ms_route_a.status == "scheduled"
    assert ms_route_a.total_stops == 3


def test_mobilesales_route_status_choices(tenant_a, admin_user):
    for status_key, _ in ROUTE_STATUS_CHOICES:
        route = _mobilesales_route(tenant_a, sales_rep=admin_user, status=status_key)
        assert route.status == status_key
        route.full_clean()


def test_mobilesales_route_optimization_status_choices(tenant_a, admin_user):
    for opt_key, _ in OPTIMIZATION_STATUS_CHOICES:
        route = _mobilesales_route(tenant_a, sales_rep=admin_user, optimization_status=opt_key)
        assert route.optimization_status == opt_key
        route.full_clean()


def test_mobilesales_route_validation_completed_stops_exceeds_total(tenant_a, admin_user):
    route = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        total_stops=3,
        completed_stops=5,
    )
    with pytest.raises(ValidationError) as exc_info:
        route.clean()
    assert "completed_stops" in exc_info.value.message_dict


def test_mobilesales_route_validation_negative_metrics(tenant_a, admin_user):
    # planned_distance_km < 0
    route_dist = _mobilesales_route(tenant_a, sales_rep=admin_user)
    route_dist.planned_distance_km = Decimal("-1.50")
    with pytest.raises(ValidationError) as exc_info:
        route_dist.clean()
    assert "planned_distance_km" in exc_info.value.message_dict

    with pytest.raises(ValidationError) as exc_info:
        route_dist.full_clean()
    assert "planned_distance_km" in exc_info.value.message_dict

    # actual_distance_km < 0
    route_actual = _mobilesales_route(tenant_a, sales_rep=admin_user)
    route_actual.actual_distance_km = Decimal("-10.00")
    with pytest.raises(ValidationError) as exc_info:
        route_actual.clean()
    assert "actual_distance_km" in exc_info.value.message_dict

    # estimated_duration_minutes < 0
    route_est = _mobilesales_route(tenant_a, sales_rep=admin_user)
    route_est.estimated_duration_minutes = -15
    with pytest.raises(ValidationError) as exc_info:
        route_est.clean()
    assert "estimated_duration_minutes" in exc_info.value.message_dict

    # actual_duration_minutes < 0
    route_act_dur = _mobilesales_route(tenant_a, sales_rep=admin_user)
    route_act_dur.actual_duration_minutes = -30
    with pytest.raises(ValidationError) as exc_info:
        route_act_dur.clean()
    assert "actual_duration_minutes" in exc_info.value.message_dict


def test_mobilesales_route_cross_tenant_sales_rep(tenant_a, admin_b):
    route = _mobilesales_route(tenant_a, sales_rep=admin_b)
    with pytest.raises(ValidationError) as exc_info:
        route.clean()
    assert "sales_rep" in exc_info.value.message_dict


def test_mobilesales_route_properties_completion_rate_and_progress(tenant_a, admin_user):
    # total_stops == 0 -> 0%
    route_zero = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=0, completed_stops=0)
    assert route_zero.completion_rate_pct == 0
    assert route_zero.progress_display == "0/0 Stops"

    # 1 of 4 stops -> 25%
    route_quarter = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=4, completed_stops=1)
    assert route_quarter.completion_rate_pct == 25
    assert route_quarter.progress_display == "1/4 Stops"

    # 2 of 3 stops -> 67%
    route_two_thirds = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=3, completed_stops=2)
    assert route_two_thirds.completion_rate_pct == 67
    assert route_two_thirds.progress_display == "2/3 Stops"

    # 5 of 5 stops -> 100%
    route_all = _mobilesales_route(tenant_a, sales_rep=admin_user, total_stops=5, completed_stops=5)
    assert route_all.completion_rate_pct == 100
    assert route_all.progress_display == "5/5 Stops"


def test_mobilesales_route_generate_navigation_url(tenant_a, admin_user):
    # Both start and end provided
    route_full = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        start_location="Market St, San Francisco, CA",
        end_location="Broadway, Oakland, CA",
    )
    url = route_full.generate_navigation_url()
    assert "https://www.google.com/maps/dir/?api=1" in url
    assert "origin=Market%20St%2C%20San%20Francisco%2C%20CA" in url
    assert "destination=Broadway%2C%20Oakland%2C%20CA" in url

    # Only start provided -> destination defaults to start
    route_start_only = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        start_location="Market St, San Francisco, CA",
        end_location="",
    )
    url_single = route_start_only.generate_navigation_url()
    assert "origin=Market%20St%2C%20San%20Francisco%2C%20CA" in url_single
    assert "destination=Market%20St%2C%20San%20Francisco%2C%20CA" in url_single

    # Empty start_location -> None
    route_empty = _mobilesales_route(
        tenant_a,
        sales_rep=admin_user,
        start_location="",
        end_location="",
    )
    assert route_empty.generate_navigation_url() is None


# ==============================================================================
# FieldCheckIn Tests
# ==============================================================================

def test_mobilesales_check_in_creation_and_str(tenant_a, ms_check_in_a):
    assert ms_check_in_a.number.startswith("CHK-")
    expected_str = f"{ms_check_in_a.number} — {ms_check_in_a.party.name} ({ms_check_in_a.check_in_at.strftime('%Y-%m-%d %H:%M')})"
    assert str(ms_check_in_a) == expected_str
    assert ms_check_in_a.tenant == tenant_a
    assert ms_check_in_a.stop_number == 1
    assert ms_check_in_a.is_geofence_verified is True


def test_mobilesales_check_in_choices(tenant_a, ms_party_a, admin_user, ms_route_a):
    for status_key, _ in VERIFICATION_STATUS_CHOICES:
        chk = _mobilesales_check_in(
            tenant_a,
            party=ms_party_a,
            sales_rep=admin_user,
            route=ms_route_a,
            verification_status=status_key,
        )
        assert chk.verification_status == status_key

    for purpose_key, _ in VISIT_PURPOSE_CHOICES:
        chk = _mobilesales_check_in(
            tenant_a,
            party=ms_party_a,
            sales_rep=admin_user,
            route=ms_route_a,
            visit_purpose=purpose_key,
        )
        assert chk.visit_purpose == purpose_key

    for outcome_key, _ in VISIT_OUTCOME_CHOICES:
        chk = _mobilesales_check_in(
            tenant_a,
            party=ms_party_a,
            sales_rep=admin_user,
            route=ms_route_a,
            outcome=outcome_key,
        )
        assert chk.outcome == outcome_key


def test_mobilesales_check_in_haversine_distance_calculation():
    # Identical coordinates -> 0.00 metres
    dist_zero = FieldCheckIn.calculate_distance(
        Decimal("37.774900"), Decimal("-122.419400"),
        Decimal("37.774900"), Decimal("-122.419400"),
    )
    assert dist_zero == Decimal("0.00")

    # None coordinate returns None
    assert FieldCheckIn.calculate_distance(None, Decimal("-122.4194"), Decimal("37.77"), Decimal("-122.41")) is None
    assert FieldCheckIn.calculate_distance(Decimal("37.77"), None, Decimal("37.77"), Decimal("-122.41")) is None

    # San Francisco (37.7749, -122.4194) to Oakland (37.8044, -122.2712)
    # Approx 13.4 km = ~13,400 m
    dist_bay = FieldCheckIn.calculate_distance(
        Decimal("37.774900"), Decimal("-122.419400"),
        Decimal("37.804400"), Decimal("-122.271200"),
    )
    assert Decimal("12000.00") < dist_bay < Decimal("15000.00")


def test_mobilesales_check_in_geofence_verification_logic(tenant_a, ms_party_a, admin_user, ms_route_a):
    # Case 1: Target very close (within 150m) -> verified
    chk_inside = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_lat=Decimal("37.774900"),
        check_in_lng=Decimal("-122.419400"),
        target_lat=Decimal("37.774950"),
        target_lng=Decimal("-122.419450"),
        geofence_radius_m=150,
        verification_status="verified",
    )
    chk_inside.clean()
    assert chk_inside.is_geofence_verified is True
    assert chk_inside.verification_status == "verified"
    assert chk_inside.distance_from_target_m < Decimal("50.00")

    # Case 2: Target far outside 150m radius -> out_of_range
    chk_outside = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_lat=Decimal("37.774900"),
        check_in_lng=Decimal("-122.419400"),
        target_lat=Decimal("37.785000"),
        target_lng=Decimal("-122.419400"),
        geofence_radius_m=150,
    )
    chk_outside.clean()
    assert chk_outside.is_geofence_verified is False
    assert chk_outside.verification_status == "out_of_range"
    assert chk_outside.distance_from_target_m > Decimal("1000.00")

    # Case 3: Manual override status preserved
    chk_override = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_lat=Decimal("37.774900"),
        check_in_lng=Decimal("-122.419400"),
        target_lat=Decimal("37.785000"),
        target_lng=Decimal("-122.419400"),
        geofence_radius_m=150,
        verification_status="manual_override",
    )
    chk_override.clean()
    assert chk_override.verification_status == "manual_override"


def test_mobilesales_check_in_duration_calculation(tenant_a, ms_party_a, admin_user, ms_route_a):
    start = timezone.now()
    end = start + timedelta(minutes=55)

    # Without check_out_at, duration is None
    chk_no_checkout = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_at=start,
    )
    assert chk_no_checkout.calculate_duration() is None

    # With both times, calculates 55 minutes
    chk_with_checkout = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_at=start,
        check_out_at=end,
        check_in_lat=Decimal("37.774900"),
        check_in_lng=Decimal("-122.419400"),
    )
    assert chk_with_checkout.calculate_duration() == 55

    # clean() auto-populates duration_minutes if unset
    assert chk_with_checkout.duration_minutes is None
    chk_with_checkout.clean()
    assert chk_with_checkout.duration_minutes == 55


def test_mobilesales_check_in_coordinate_validation(tenant_a, ms_party_a, admin_user, ms_route_a):
    # Invalid arrival latitude (> 90)
    chk = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_lat=Decimal("95.000000"),
        check_in_lng=Decimal("-122.419400"),
    )
    with pytest.raises(ValidationError) as exc:
        chk.clean()
    assert "check_in_lat" in exc.value.message_dict

    # Invalid arrival longitude (< -180)
    chk.check_in_lat = Decimal("37.774900")
    chk.check_in_lng = Decimal("-185.000000")
    with pytest.raises(ValidationError) as exc:
        chk.clean()
    assert "check_in_lng" in exc.value.message_dict

    # Invalid departure latitude (< -90)
    chk.check_in_lng = Decimal("-122.419400")
    chk.check_out_lat = Decimal("-95.000000")
    with pytest.raises(ValidationError) as exc:
        chk.clean()
    assert "check_out_lat" in exc.value.message_dict

    # Invalid departure longitude (> 180)
    chk.check_out_lat = Decimal("37.774900")
    chk.check_out_lng = Decimal("195.000000")
    with pytest.raises(ValidationError) as exc:
        chk.clean()
    assert "check_out_lng" in exc.value.message_dict


def test_mobilesales_check_in_checkout_before_checkin_validation(tenant_a, ms_party_a, admin_user, ms_route_a):
    now = timezone.now()
    chk = FieldCheckIn(
        tenant=tenant_a,
        party=ms_party_a,
        sales_rep=admin_user,
        route=ms_route_a,
        check_in_at=now,
        check_out_at=now - timedelta(minutes=10),
        check_in_lat=Decimal("37.774900"),
        check_in_lng=Decimal("-122.419400"),
    )
    with pytest.raises(ValidationError) as exc:
        chk.clean()
    assert "check_out_at" in exc.value.message_dict


def test_mobilesales_check_in_cross_tenant_isolation(
    tenant_a, tenant_b, ms_party_a, ms_party_b, admin_user, admin_b, ms_route_a, ms_route_b
):
    base_kwargs = {
        "tenant": tenant_a,
        "party": ms_party_a,
        "sales_rep": admin_user,
        "route": ms_route_a,
        "check_in_lat": Decimal("37.774900"),
        "check_in_lng": Decimal("-122.419400"),
    }

    # Party from tenant_b
    chk_bad_party = FieldCheckIn(**{**base_kwargs, "party": ms_party_b})
    with pytest.raises(ValidationError) as exc:
        chk_bad_party.clean()
    assert "party" in exc.value.message_dict

    # Sales rep from tenant_b
    chk_bad_rep = FieldCheckIn(**{**base_kwargs, "sales_rep": admin_b})
    with pytest.raises(ValidationError) as exc:
        chk_bad_rep.clean()
    assert "sales_rep" in exc.value.message_dict

    # Route from tenant_b
    chk_bad_route = FieldCheckIn(**{**base_kwargs, "route": ms_route_b})
    with pytest.raises(ValidationError) as exc:
        chk_bad_route.clean()
    assert "route" in exc.value.message_dict

    # Contact from tenant_b
    chk_bad_contact = FieldCheckIn(**{**base_kwargs, "contact": ms_party_b})
    with pytest.raises(ValidationError) as exc:
        chk_bad_contact.clean()
    assert "contact" in exc.value.message_dict

    # Opportunity from tenant_b
    opp_b = _mobilesales_opportunity(tenant_b, name="Tenant B Deal")
    chk_bad_opp = FieldCheckIn(**{**base_kwargs, "opportunity": opp_b})
    with pytest.raises(ValidationError) as exc:
        chk_bad_opp.clean()
    assert "opportunity" in exc.value.message_dict

    # Communication log from tenant_b
    log_b = _mobilesales_communication_log(tenant_b, owner=admin_b)
    chk_bad_log = FieldCheckIn(**{**base_kwargs, "communication_log": log_b})
    with pytest.raises(ValidationError) as exc:
        chk_bad_log.clean()
    assert "communication_log" in exc.value.message_dict


# ==============================================================================
# MobileDeviceSession Tests
# ==============================================================================

def test_mobilesales_device_creation_and_str(tenant_a, ms_device_a):
    assert ms_device_a.number.startswith("MDS-")
    expected_str = f"{ms_device_a.number} — {ms_device_a.device_name} ({ms_device_a.user.username})"
    assert str(ms_device_a) == expected_str
    assert ms_device_a.tenant == tenant_a
    assert ms_device_a.platform == "ios"
    assert ms_device_a.is_active is True
    assert ms_device_a.is_trusted is True


def test_mobilesales_device_platform_and_sync_choices(tenant_a, admin_user):
    for plat_key, _ in PLATFORM_CHOICES:
        dev = _mobilesales_device(tenant_a, user=admin_user, platform=plat_key, device_uuid=f"uuid-{plat_key}")
        assert dev.platform == plat_key
        dev.full_clean()

    for sync_key, _ in SYNC_STATUS_CHOICES:
        dev = _mobilesales_device(tenant_a, user=admin_user, last_sync_status=sync_key, device_uuid=f"uuid-{sync_key}")
        assert dev.last_sync_status == sync_key
        dev.full_clean()


def test_mobilesales_device_record_sync_event(tenant_a, ms_device_a):
    ms_device_a.record_sync_event(
        status="success",
        cached_count=245,
        pending_count=3,
        ip="192.168.1.15",
    )
    ms_device_a.refresh_from_db()

    assert ms_device_a.last_sync_status == "success"
    assert ms_device_a.offline_records_cached == 245
    assert ms_device_a.pending_uploads_count == 3
    assert ms_device_a.last_ip_address == "192.168.1.15"
    assert ms_device_a.last_sync_at is not None
    assert (timezone.now() - ms_device_a.last_sync_at).total_seconds() < 10


def test_mobilesales_device_is_outdated_property(tenant_a, admin_user):
    # No sync yet -> outdated
    dev_unsynced = _mobilesales_device(tenant_a, user=admin_user, device_uuid="uuid-outdated-1", last_sync_at=None)
    assert dev_unsynced.is_outdated is True

    # Sync > 24 hours ago -> outdated
    past_sync = timezone.now() - timedelta(hours=25)
    dev_stale = _mobilesales_device(tenant_a, user=admin_user, device_uuid="uuid-outdated-2", last_sync_at=past_sync)
    assert dev_stale.is_outdated is True

    # Sync 2 hours ago -> fresh
    recent_sync = timezone.now() - timedelta(hours=2)
    dev_fresh = _mobilesales_device(tenant_a, user=admin_user, device_uuid="uuid-outdated-3", last_sync_at=recent_sync)
    assert dev_fresh.is_outdated is False


def test_mobilesales_device_cross_tenant_user_clean(tenant_a, admin_b):
    dev = _mobilesales_device(tenant_a, user=admin_b, device_uuid="uuid-cross-tenant")
    with pytest.raises(ValidationError) as exc:
        dev.clean()
    assert "user" in exc.value.message_dict


# ==============================================================================
# MobileDealAlert Tests
# ==============================================================================

def test_mobilesales_alert_creation_and_str(tenant_a, ms_alert_a):
    assert ms_alert_a.number.startswith("MDA-")
    expected_str = f"{ms_alert_a.number} — {ms_alert_a.title} ({ms_alert_a.get_urgency_display()})"
    assert str(ms_alert_a) == expected_str
    assert ms_alert_a.tenant == tenant_a
    assert ms_alert_a.urgency == "urgent"
    assert ms_alert_a.is_read is False


def test_mobilesales_alert_choices(tenant_a, admin_user, ms_device_a):
    for alert_key, _ in ALERT_TYPE_CHOICES:
        alert = _mobilesales_alert(tenant_a, recipient=admin_user, device=ms_device_a, alert_type=alert_key)
        assert alert.alert_type == alert_key
        alert.full_clean()

    for urgency_key, _ in URGENCY_CHOICES:
        alert = _mobilesales_alert(tenant_a, recipient=admin_user, device=ms_device_a, urgency=urgency_key)
        assert alert.urgency == urgency_key
        alert.full_clean()

    for push_key, _ in PUSH_STATUS_CHOICES:
        alert = _mobilesales_alert(tenant_a, recipient=admin_user, device=ms_device_a, push_status=push_key)
        assert alert.push_status == push_key
        alert.full_clean()


def test_mobilesales_alert_mark_as_read(tenant_a, ms_alert_a):
    assert ms_alert_a.is_read is False
    assert ms_alert_a.read_at is None

    ms_alert_a.mark_as_read()
    ms_alert_a.refresh_from_db()

    assert ms_alert_a.is_read is True
    assert ms_alert_a.read_at is not None
    assert (timezone.now() - ms_alert_a.read_at).total_seconds() < 10


def test_mobilesales_alert_dispatch(tenant_a, ms_alert_a):
    ms_alert_a.push_status = "pending"
    ms_alert_a.push_sent_at = None
    ms_alert_a.save()

    ms_alert_a.dispatch_alert()
    ms_alert_a.refresh_from_db()

    assert ms_alert_a.push_status == "sent"
    assert ms_alert_a.push_sent_at is not None
    assert (timezone.now() - ms_alert_a.push_sent_at).total_seconds() < 10


def test_mobilesales_alert_cross_tenant_isolation(
    tenant_a, tenant_b, admin_user, admin_b, ms_device_a, ms_device_b, ms_route_b
):
    base_kwargs = {
        "tenant": tenant_a,
        "recipient": admin_user,
        "device": ms_device_a,
        "title": "Alert Test",
        "message": "Urgent update",
    }

    # Recipient belongs to tenant_b
    alert_bad_rep = MobileDealAlert(**{**base_kwargs, "recipient": admin_b})
    with pytest.raises(ValidationError) as exc:
        alert_bad_rep.clean()
    assert "recipient" in exc.value.message_dict

    # Device belongs to tenant_b
    alert_bad_dev = MobileDealAlert(**{**base_kwargs, "device": ms_device_b})
    with pytest.raises(ValidationError) as exc:
        alert_bad_dev.clean()
    assert "device" in exc.value.message_dict

    # Route belongs to tenant_b
    alert_bad_route = MobileDealAlert(**{**base_kwargs, "related_route": ms_route_b})
    with pytest.raises(ValidationError) as exc:
        alert_bad_route.clean()
    assert "related_route" in exc.value.message_dict

    # Opportunity belongs to tenant_b
    opp_b = _mobilesales_opportunity(tenant_b, name="Cross Tenant Alert Deal")
    alert_bad_opp = MobileDealAlert(**{**base_kwargs, "related_opportunity": opp_b})
    with pytest.raises(ValidationError) as exc:
        alert_bad_opp.clean()
    assert "related_opportunity" in exc.value.message_dict
