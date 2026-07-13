"""Tests for HRM 3.35 Travel Management sub-module: ``TravelPolicy`` (admin-config CRUD, class-of-
travel/hotel/advance caps) + ``TravelRequest`` (own-vs-admin CRUD, ``TRV-#####``, the single-approver
workflow reused VERBATIM from 3.26's ``_hr_request_*`` helpers) + bespoke advance
approve/pay/settlement/complete actions + inline ``TravelBooking`` (draft/pending-only, document
uploads, computed ``out_of_policy``).

Mirrors ``test_expenses.py`` / ``test_assets.py`` — same fixture style (local ``pytest.fixture``s in
this module reusing the shared root/HRM conftest), hand-verified computed properties, IDOR,
access-control, own-vs-admin self-service scoping (``_ss_scope`` / ``_can_manage_own_child`` — the
same 3.25/3.26 helpers), self-approval blocks (``_is_own_hr_request``), and a query-count-ceiling
regression guard.

Covers:
  - ``TravelBooking.out_of_policy``/``out_of_policy_reason`` (flight class-rank + hotel per-night,
    the nights=1 fallback, and every None-guard) and ``TravelRequest.net_settlement`` (None / positive
    payable / negative recoverable, built off a REAL linked 3.34 ``ExpenseClaim``).
  - Model basics (auto-number ``TRV-#####``, ``__str__``, defaults, ``unique_together``).
  - ``TravelPolicyForm``/``TravelRequestForm`` (incl. the policy-trip_type cross-check)/
    ``TravelBookingForm`` (incl. the shared document upload guard) validation.
  - Full CRUD + the single-approver workflow (create/submit/approve/reject/cancel/complete), the
    OPEN_STATUSES edit/delete gate, the bespoke advance approve/pay actions (incl. the NaN-safe-500
    guard) and settlement generation (idempotent, creates a linked 3.34 ExpenseClaim).
  - Inline ``TravelBooking`` CRUD (draft/pending-only, document upload).
  - ``travelpolicy_delete`` guard (blocked while referenced by a request).
  - Self-approval / maker-checker blocks on approve/reject/approve_advance/mark_advance_paid.
  - Access control (anonymous redirect, non-admin 403 on admin-only actions), own-vs-admin
    self-service scoping + cross-employee IDOR (403), multi-tenant IDOR (404 + list isolation),
    CSRF enforcement, and an N+1 query-count-ceiling regression guard on ``travelrequest_list``.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Shared fixtures
# ============================================================

def _client_for(party, tenant, *, email, username, is_admin=False):
    """A fresh logged-in Client for a NEW user linked (via ``party``) to an EmployeeProfile —
    mirrors ``test_expenses.py``'s helper for own-vs-admin / self-approval fixtures."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email=email, username=username, password="TestPass123!",
        tenant=tenant, is_tenant_admin=is_admin,
    )
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def own_client(tenant_a, employee_a):
    """A NON-ADMIN user whose linked EmployeeProfile IS employee_a — the 'owner' for own-vs-admin
    scoping tests (sees/manages only employee_a's trips)."""
    return _client_for(employee_a.party, tenant_a, email="owner@acme.com", username="owner_acme")


@pytest.fixture
def other_employee_client(tenant_a, employee_a2):
    """A NON-ADMIN user whose linked EmployeeProfile IS employee_a2 — a DIFFERENT employee from
    employee_a, same tenant (cross-employee IDOR probes)."""
    return _client_for(employee_a2.party, tenant_a, email="other@acme.com", username="other_acme")


@pytest.fixture
def self_admin_client(tenant_a, employee_a):
    """A TENANT ADMIN whose linked EmployeeProfile IS employee_a — the self-approval-block subject
    (an admin who is ALSO the trip's employee)."""
    return _client_for(employee_a.party, tenant_a, email="selfadmin@acme.com",
                        username="selfadmin_acme", is_admin=True)


@pytest.fixture
def travel_policy_a(db, tenant_a):
    """A TravelPolicy for tenant_a — economy class, hotel_limit_per_night=200, advance cap 80%."""
    from apps.hrm.models import TravelPolicy
    return TravelPolicy.objects.create(
        tenant=tenant_a, name="Standard Economy", trip_type="both", travel_class="economy",
        daily_allowance_limit=Decimal("100.00"), hotel_limit_per_night=Decimal("200.00"),
        advance_percent_limit=Decimal("80.00"), is_active=True,
    )


@pytest.fixture
def travel_policy_b(db, tenant_b):
    """A TravelPolicy belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TravelPolicy
    return TravelPolicy.objects.create(
        tenant=tenant_b, name="Globex Economy", trip_type="both", travel_class="economy",
    )


@pytest.fixture
def draft_trip_a(db, tenant_a, employee_a, travel_policy_a):
    """A draft TravelRequest for employee_a/tenant_a, linked to travel_policy_a, estimated_cost=1000."""
    from apps.hrm.models import TravelRequest
    return TravelRequest.objects.create(
        tenant=tenant_a, employee=employee_a, title="Client Site Visit", trip_type="domestic",
        origin="New York, NY", destination="San Francisco, CA", purpose="Client meeting",
        start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 5),
        policy=travel_policy_a, estimated_cost=Decimal("1000.00"),
    )


@pytest.fixture
def pending_trip_a(db, draft_trip_a):
    """draft_trip_a flipped to pending (submitted) — the approve/reject pre-req."""
    draft_trip_a.status = "pending"
    draft_trip_a.save(update_fields=["status", "updated_at"])
    return draft_trip_a


@pytest.fixture
def approved_trip_a(db, tenant_a, employee_a, travel_policy_a, admin_user):
    """An INDEPENDENT approved TravelRequest for employee_a — advance_requested=500 (cap: 80% of
    1000 = 800, so advance_requested itself is the binding constraint, not the policy cap) — the
    advance-approve / mark-paid / settlement / complete pre-req."""
    from apps.hrm.models import TravelRequest
    return TravelRequest.objects.create(
        tenant=tenant_a, employee=employee_a, title="Approved Business Trip", trip_type="domestic",
        origin="New York, NY", destination="Los Angeles, CA", purpose="Sales conference",
        start_date=datetime.date(2026, 8, 10), end_date=datetime.date(2026, 8, 14),
        policy=travel_policy_a, estimated_cost=Decimal("1000.00"), advance_requested=Decimal("500.00"),
        status="approved", approver=admin_user, approved_at=timezone.now(),
    )


@pytest.fixture
def approved_trip_no_advance_requested_a(db, tenant_a, employee_a, admin_user):
    """An approved TravelRequest with NO advance_requested (None) — isolates the "no advance was
    requested" approve_advance guard."""
    from apps.hrm.models import TravelRequest
    return TravelRequest.objects.create(
        tenant=tenant_a, employee=employee_a, title="No Advance Trip", trip_type="domestic",
        origin="NYC", destination="Boston", purpose="Client visit",
        start_date=datetime.date(2026, 8, 10), end_date=datetime.date(2026, 8, 12),
        estimated_cost=Decimal("500.00"), status="approved", approver=admin_user,
        approved_at=timezone.now(),
    )


@pytest.fixture
def approved_trip_with_cap_a(db, tenant_a, employee_a, admin_user):
    """An approved TravelRequest whose advance_requested (900) is safely ABOVE the policy's 80% cap
    of estimated_cost (1000 * 0.80 = 800) — isolates the %-cap boundary check from the
    advance_requested ceiling."""
    from apps.hrm.models import TravelPolicy, TravelRequest
    policy = TravelPolicy.objects.create(
        tenant=tenant_a, name="Capped Policy", trip_type="both", travel_class="business",
        advance_percent_limit=Decimal("80.00"),
    )
    return TravelRequest.objects.create(
        tenant=tenant_a, employee=employee_a, title="Cap Boundary Trip", trip_type="domestic",
        origin="NYC", destination="Chicago", purpose="Business",
        start_date=datetime.date(2026, 8, 10), end_date=datetime.date(2026, 8, 14),
        policy=policy, estimated_cost=Decimal("1000.00"), advance_requested=Decimal("900.00"),
        status="approved", approver=admin_user, approved_at=timezone.now(),
    )


@pytest.fixture
def approved_trip_with_paid_advance_a(db, tenant_a, employee_a, admin_user):
    """An approved TravelRequest with an already-APPROVED advance (500), not yet paid — the
    mark_advance_paid success/idempotency pre-req."""
    from apps.hrm.models import TravelRequest
    return TravelRequest.objects.create(
        tenant=tenant_a, employee=employee_a, title="Paid Advance Trip", trip_type="domestic",
        origin="NYC", destination="Denver", purpose="Business",
        start_date=datetime.date(2026, 8, 10), end_date=datetime.date(2026, 8, 14),
        estimated_cost=Decimal("1000.00"), advance_requested=Decimal("500.00"),
        advance_approved=Decimal("500.00"), status="approved", approver=admin_user,
        approved_at=timezone.now(),
    )


@pytest.fixture
def trip_b(db, tenant_b, employee_b, travel_policy_b):
    """A draft TravelRequest belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TravelRequest
    return TravelRequest.objects.create(
        tenant=tenant_b, employee=employee_b, title="Globex Trip", trip_type="domestic",
        origin="Chicago, IL", destination="Miami, FL", purpose="Sales",
        start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 5),
        policy=travel_policy_b,
    )


@pytest.fixture
def booking_a(db, tenant_a, draft_trip_a):
    """A flight TravelBooking on draft_trip_a (OPEN status) — economy class, clean."""
    from apps.hrm.models import TravelBooking
    return TravelBooking.objects.create(
        tenant=tenant_a, travel_request=draft_trip_a, booking_type="flight", vendor="Delta Airlines",
        reference="ABC123", depart_date=datetime.date(2026, 8, 1), return_date=datetime.date(2026, 8, 5),
        travel_class="economy", cost=Decimal("400.00"),
    )


@pytest.fixture
def booking_on_approved_a(db, tenant_a, approved_trip_a):
    """A TravelBooking on approved_trip_a (NOT an OPEN status) — the edit/delete-blocked pre-req."""
    from apps.hrm.models import TravelBooking
    return TravelBooking.objects.create(
        tenant=tenant_a, travel_request=approved_trip_a, booking_type="hotel", vendor="Marriott",
        cost=Decimal("200.00"),
    )


@pytest.fixture
def booking_b(db, tenant_b, trip_b):
    """A TravelBooking belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TravelBooking
    return TravelBooking.objects.create(
        tenant=tenant_b, travel_request=trip_b, booking_type="flight", vendor="United Airlines",
        cost=Decimal("300.00"),
    )


@pytest.fixture
def expense_category_a(db, tenant_a):
    """An ExpenseCategory for tenant_a — the 3.34 settlement-claim line pre-req."""
    from apps.hrm.models import ExpenseCategory
    return ExpenseCategory.objects.create(tenant=tenant_a, name="Travel Settlement", code="TRVSTL")


@pytest.fixture
def many_travel_requests_a(db, tenant_a, employee_a, employee_a2):
    """12 TravelRequests for tenant_a (split across employee_a/employee_a2) — the N+1 query-count
    fixture for travelrequest_list."""
    from apps.hrm.models import TravelRequest
    trips = []
    for i in range(12):
        emp = employee_a if i % 2 == 0 else employee_a2
        trips.append(TravelRequest.objects.create(
            tenant=tenant_a, employee=emp, title=f"Bulk Trip {i}", trip_type="domestic",
            origin="NYC", destination="LA", purpose="Bulk",
            start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 5),
        ))
    return trips


def _travel_policy_payload(**overrides):
    """A minimal-but-complete valid TravelPolicyForm POST payload."""
    data = {
        "name": "New Policy", "job_grade": "", "trip_type": "both", "travel_class": "economy",
        "daily_allowance_limit": "", "hotel_limit_per_night": "", "advance_percent_limit": "",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def _travel_request_payload(**overrides):
    """A minimal-but-complete valid TravelRequestForm POST payload."""
    data = {
        "title": "New Trip", "trip_type": "domestic", "origin": "New York, NY",
        "destination": "San Francisco, CA", "purpose": "Client meeting",
        "start_date": "2026-08-01", "end_date": "2026-08-05",
        "policy": "", "estimated_cost": "", "currency": "", "advance_requested": "",
    }
    data.update(overrides)
    return data


def _travel_booking_payload(**overrides):
    """A minimal-but-complete valid TravelBookingForm POST payload (no document by default)."""
    data = {
        "booking_type": "flight", "vendor": "Delta Airlines", "reference": "XYZ789",
        "depart_date": "2026-08-01", "return_date": "2026-08-05", "travel_class": "economy",
        "cost": "400.00", "notes": "",
    }
    data.update(overrides)
    return data


# ============================================================
# 1. TravelBooking.out_of_policy (hand-verified)
# ============================================================

class TestTravelBookingOutOfPolicyFlight:
    def test_business_under_economy_policy_flags(self, tenant_a, draft_trip_a):
        """Policy class = economy; booking class = business -> exceeds -> True."""
        from apps.hrm.models import TravelBooking
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="flight", vendor="Delta",
            travel_class="business", cost=Decimal("1200.00"),
        )
        assert booking.out_of_policy is True
        assert "exceeds the policy limit of Economy" in booking.out_of_policy_reason

    def test_economy_under_business_policy_is_clean(self, tenant_a, employee_a, travel_policy_a):
        """Policy class = business; booking class = economy -> within limit -> False."""
        from apps.hrm.models import TravelPolicy, TravelRequest, TravelBooking
        policy = TravelPolicy.objects.create(
            tenant=tenant_a, name="Business Policy", trip_type="both", travel_class="business",
        )
        trip = TravelRequest.objects.create(
            tenant=tenant_a, employee=employee_a, title="Exec Trip", trip_type="domestic",
            origin="NYC", destination="LA", purpose="Exec review",
            start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 5), policy=policy,
        )
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=trip, booking_type="flight", vendor="United",
            travel_class="economy", cost=Decimal("400.00"),
        )
        assert booking.out_of_policy is False
        assert booking.out_of_policy_reason == ""

    def test_matching_class_is_clean(self, tenant_a, draft_trip_a):
        """Booking class == policy class -> rank not exceeded -> False."""
        from apps.hrm.models import TravelBooking
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="flight", vendor="Delta",
            travel_class="economy", cost=Decimal("400.00"),
        )
        assert booking.out_of_policy is False


class TestTravelBookingOutOfPolicyHotel:
    def test_cost_per_night_over_limit_flags(self, tenant_a, draft_trip_a):
        """cost=500 over 2 nights = 250/night > policy hotel_limit_per_night=200 -> True."""
        from apps.hrm.models import TravelBooking
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="hotel", vendor="Marriott",
            depart_date=datetime.date(2026, 8, 1), return_date=datetime.date(2026, 8, 3),
            cost=Decimal("500.00"),
        )
        assert booking.out_of_policy is True
        assert "exceeds the policy limit of 200.00/night" in booking.out_of_policy_reason

    def test_cost_per_night_under_limit_is_clean(self, tenant_a, draft_trip_a):
        """cost=300 over 2 nights = 150/night < 200 -> False."""
        from apps.hrm.models import TravelBooking
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="hotel", vendor="Marriott",
            depart_date=datetime.date(2026, 8, 1), return_date=datetime.date(2026, 8, 3),
            cost=Decimal("300.00"),
        )
        assert booking.out_of_policy is False
        assert booking.out_of_policy_reason == ""

    def test_missing_dates_falls_back_to_one_night_no_crash(self, tenant_a, draft_trip_a):
        """No depart/return dates -> nights=1 fallback -> per_night == cost, no ZeroDivisionError."""
        from apps.hrm.models import TravelBooking
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="hotel", vendor="Marriott",
            cost=Decimal("250.00"),
        )
        assert booking.out_of_policy is True  # 250/1 > 200

    def test_invalid_date_order_falls_back_to_one_night_no_crash(self, tenant_a, draft_trip_a):
        """return_date <= depart_date (same day) -> nights=1 fallback, no crash."""
        from apps.hrm.models import TravelBooking
        same_day = datetime.date(2026, 8, 1)
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="hotel", vendor="Marriott",
            depart_date=same_day, return_date=same_day, cost=Decimal("150.00"),
        )
        assert booking.out_of_policy is False  # 150/1 <= 200

    def test_no_policy_guard_never_flags(self, tenant_a, employee_a):
        """travel_request.policy is None -> always False regardless of cost."""
        from apps.hrm.models import TravelRequest, TravelBooking
        trip = TravelRequest.objects.create(
            tenant=tenant_a, employee=employee_a, title="No Policy Trip", trip_type="domestic",
            origin="NYC", destination="LA", purpose="Business",
            start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 5),
        )
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=trip, booking_type="hotel", vendor="Marriott",
            cost=Decimal("99999.00"),
        )
        assert booking.out_of_policy is False
        assert booking.out_of_policy_reason == ""

    def test_missing_cost_guard_never_flags(self, tenant_a, draft_trip_a):
        """cost=None -> the hotel branch is skipped entirely -> False."""
        from apps.hrm.models import TravelBooking
        booking = TravelBooking.objects.create(
            tenant=tenant_a, travel_request=draft_trip_a, booking_type="hotel", vendor="Marriott",
            cost=None,
        )
        assert booking.out_of_policy is False


# ============================================================
# 2. TravelRequest.net_settlement (hand-verified, real linked ExpenseClaim)
# ============================================================

class TestTravelRequestNetSettlement:
    def test_no_settlement_claim_is_none(self, approved_trip_a):
        assert approved_trip_a.net_settlement is None

    def test_positive_payable_to_employee(self, tenant_a, approved_trip_a, expense_category_a):
        """total_amount (100) - advance_approved (40) = 60 -> POSITIVE (payable to employee)."""
        from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
        claim = ExpenseClaim.objects.create(
            tenant=tenant_a, employee=approved_trip_a.employee, title="Settlement")
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=claim, category=expense_category_a,
            expense_date=datetime.date(2026, 8, 12), amount=Decimal("60.00"))
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=claim, category=expense_category_a,
            expense_date=datetime.date(2026, 8, 13), amount=Decimal("40.00"))
        approved_trip_a.settlement_claim = claim
        approved_trip_a.advance_approved = Decimal("40.00")
        approved_trip_a.save(update_fields=["settlement_claim", "advance_approved"])
        assert approved_trip_a.net_settlement == Decimal("60.00")

    def test_negative_recoverable_from_employee(self, tenant_a, approved_trip_a, expense_category_a):
        """total_amount (100) - advance_approved (150) = -50 -> NEGATIVE (recoverable)."""
        from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
        claim = ExpenseClaim.objects.create(
            tenant=tenant_a, employee=approved_trip_a.employee, title="Settlement")
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=claim, category=expense_category_a,
            expense_date=datetime.date(2026, 8, 12), amount=Decimal("100.00"))
        approved_trip_a.settlement_claim = claim
        approved_trip_a.advance_approved = Decimal("150.00")
        approved_trip_a.save(update_fields=["settlement_claim", "advance_approved"])
        assert approved_trip_a.net_settlement == Decimal("-50.00")

    def test_no_advance_approved_defaults_to_zero(self, tenant_a, approved_trip_a, expense_category_a):
        """advance_approved is None -> treated as 0 -> net_settlement == total_amount."""
        from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
        claim = ExpenseClaim.objects.create(
            tenant=tenant_a, employee=approved_trip_a.employee, title="Settlement")
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=claim, category=expense_category_a,
            expense_date=datetime.date(2026, 8, 12), amount=Decimal("75.00"))
        approved_trip_a.settlement_claim = claim
        approved_trip_a.save(update_fields=["settlement_claim"])
        assert approved_trip_a.net_settlement == Decimal("75.00")


# ============================================================
# 3. Model basics
# ============================================================

class TestTravelPolicyModelBasics:
    def test_str(self, travel_policy_a):
        assert str(travel_policy_a) == f"{travel_policy_a.name} ({travel_policy_a.get_travel_class_display()})"

    def test_default_is_active_true(self, tenant_a):
        from apps.hrm.models import TravelPolicy
        obj = TravelPolicy.objects.create(tenant=tenant_a, name="Defaults")
        assert obj.is_active is True

    def test_default_trip_type_both(self, tenant_a):
        from apps.hrm.models import TravelPolicy
        obj = TravelPolicy.objects.create(tenant=tenant_a, name="Defaults2")
        assert obj.trip_type == "both"

    def test_unique_together_tenant_name(self, tenant_a, travel_policy_a):
        from django.db import IntegrityError, transaction
        from apps.hrm.models import TravelPolicy
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TravelPolicy.objects.create(tenant=tenant_a, name=travel_policy_a.name)


class TestTravelRequestModelBasics:
    def test_str_includes_number_and_destination(self, draft_trip_a):
        assert draft_trip_a.number in str(draft_trip_a)
        assert draft_trip_a.destination in str(draft_trip_a)

    def test_number_prefix(self, draft_trip_a):
        assert draft_trip_a.number.startswith("TRV-")

    def test_default_status_draft(self, draft_trip_a):
        assert draft_trip_a.status == "draft"

    def test_unique_together_tenant_number(self, tenant_a, draft_trip_a, employee_a):
        from django.db import IntegrityError, transaction
        from apps.hrm.models import TravelRequest
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                TravelRequest.objects.create(
                    tenant=tenant_a, employee=employee_a, title="Dup", origin="X", destination="Y",
                    purpose="Z", start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 2),
                    number=draft_trip_a.number)


class TestTravelBookingModelBasics:
    def test_str(self, booking_a, draft_trip_a):
        s = str(booking_a)
        assert draft_trip_a.number in s
        assert booking_a.vendor in s

    def test_default_booking_type_flight(self, tenant_a, draft_trip_a):
        from apps.hrm.models import TravelBooking
        obj = TravelBooking.objects.create(tenant=tenant_a, travel_request=draft_trip_a, vendor="Test")
        assert obj.booking_type == "flight"


# ============================================================
# 4. Forms
# ============================================================

class TestTravelPolicyForm:
    def test_valid_payload_passes(self, tenant_a):
        from apps.hrm.forms import TravelPolicyForm
        form = TravelPolicyForm(data=_travel_policy_payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_advance_percent_over_100_rejected(self, tenant_a):
        from apps.hrm.forms import TravelPolicyForm
        form = TravelPolicyForm(data=_travel_policy_payload(advance_percent_limit="150"), tenant=tenant_a)
        assert not form.is_valid()
        assert "advance_percent_limit" in form.errors

    def test_advance_percent_negative_rejected(self, tenant_a):
        from apps.hrm.forms import TravelPolicyForm
        form = TravelPolicyForm(data=_travel_policy_payload(advance_percent_limit="-5"), tenant=tenant_a)
        assert not form.is_valid()
        assert "advance_percent_limit" in form.errors

    def test_daily_allowance_negative_rejected(self, tenant_a):
        from apps.hrm.forms import TravelPolicyForm
        form = TravelPolicyForm(data=_travel_policy_payload(daily_allowance_limit="-1"), tenant=tenant_a)
        assert not form.is_valid()
        assert "daily_allowance_limit" in form.errors

    def test_hotel_limit_negative_rejected(self, tenant_a):
        from apps.hrm.forms import TravelPolicyForm
        form = TravelPolicyForm(data=_travel_policy_payload(hotel_limit_per_night="-1"), tenant=tenant_a)
        assert not form.is_valid()
        assert "hotel_limit_per_night" in form.errors

    def test_tenant_and_name_uniqueness_fields_not_excluded_oddly(self):
        from apps.hrm.forms import TravelPolicyForm
        assert "tenant" not in TravelPolicyForm.Meta.fields


class TestTravelRequestForm:
    def test_valid_payload_passes(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(data=_travel_request_payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_end_date_before_start_date_rejected(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(
            data=_travel_request_payload(start_date="2026-08-10", end_date="2026-08-01"), tenant=tenant_a)
        assert not form.is_valid()
        assert "end_date" in form.errors

    def test_end_date_equal_start_date_passes(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(
            data=_travel_request_payload(start_date="2026-08-10", end_date="2026-08-10"), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_advance_requested_over_estimated_cost_rejected(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(
            data=_travel_request_payload(estimated_cost="1000", advance_requested="1500"), tenant=tenant_a)
        assert not form.is_valid()
        assert "advance_requested" in form.errors

    def test_advance_requested_equal_estimated_cost_passes(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(
            data=_travel_request_payload(estimated_cost="1000", advance_requested="1000"), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_negative_estimated_cost_rejected(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(data=_travel_request_payload(estimated_cost="-10"), tenant=tenant_a)
        assert not form.is_valid()
        assert "estimated_cost" in form.errors

    def test_negative_advance_requested_rejected(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        form = TravelRequestForm(data=_travel_request_payload(advance_requested="-10"), tenant=tenant_a)
        assert not form.is_valid()
        assert "advance_requested" in form.errors

    def test_policy_trip_type_mismatch_rejected(self, tenant_a):
        """A domestic-only policy applied to an international request is rejected."""
        from apps.hrm.forms import TravelRequestForm
        from apps.hrm.models import TravelPolicy
        policy = TravelPolicy.objects.create(tenant=tenant_a, name="Domestic Only", trip_type="domestic")
        form = TravelRequestForm(
            data=_travel_request_payload(policy=policy.pk, trip_type="international"), tenant=tenant_a)
        assert not form.is_valid()
        assert "policy" in form.errors

    def test_policy_trip_type_match_passes(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        from apps.hrm.models import TravelPolicy
        policy = TravelPolicy.objects.create(tenant=tenant_a, name="Domestic Only 2", trip_type="domestic")
        form = TravelRequestForm(
            data=_travel_request_payload(policy=policy.pk, trip_type="domestic"), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_policy_scoped_both_always_passes(self, tenant_a):
        from apps.hrm.forms import TravelRequestForm
        from apps.hrm.models import TravelPolicy
        policy = TravelPolicy.objects.create(tenant=tenant_a, name="Both Scope", trip_type="both")
        form = TravelRequestForm(
            data=_travel_request_payload(policy=policy.pk, trip_type="international"), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_policy_queryset_excludes_cross_tenant_and_inactive(self, tenant_a, travel_policy_b):
        from apps.hrm.forms import TravelRequestForm
        from apps.hrm.models import TravelPolicy
        inactive = TravelPolicy.objects.create(
            tenant=tenant_a, name="Inactive Policy", trip_type="both", is_active=False)
        form = TravelRequestForm(tenant=tenant_a)
        pks = list(form.fields["policy"].queryset.values_list("pk", flat=True))
        assert travel_policy_b.pk not in pks
        assert inactive.pk not in pks

    def test_currency_queryset_excludes_inactive(self, tenant_a):
        from apps.accounting.models import Currency
        from apps.hrm.forms import TravelRequestForm
        active = Currency.objects.create(code="USD", name="US Dollar", is_active=True)
        inactive = Currency.objects.create(code="ZZZ", name="Inactive", is_active=False)
        form = TravelRequestForm(tenant=tenant_a)
        pks = list(form.fields["currency"].queryset.values_list("pk", flat=True))
        assert active.pk in pks
        assert inactive.pk not in pks

    def test_workflow_owned_fields_not_form_fields(self):
        from apps.hrm.forms import TravelRequestForm
        for field in ("status", "employee", "tenant", "number", "approver", "approved_at",
                      "decision_note", "advance_approved", "advance_paid_at", "advance_reference",
                      "settlement_claim"):
            assert field not in TravelRequestForm.Meta.fields


class TestTravelBookingForm:
    def test_valid_payload_passes(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm
        form = TravelBookingForm(data=_travel_booking_payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_return_date_before_depart_date_rejected(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm
        form = TravelBookingForm(
            data=_travel_booking_payload(depart_date="2026-08-10", return_date="2026-08-01"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "return_date" in form.errors

    def test_negative_cost_rejected(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm
        form = TravelBookingForm(data=_travel_booking_payload(cost="-5"), tenant=tenant_a)
        assert not form.is_valid()
        assert "cost" in form.errors

    def test_pdf_document_accepted(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm
        pdf = SimpleUploadedFile("itinerary.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        form = TravelBookingForm(_travel_booking_payload(), {"document": pdf}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_png_document_accepted(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm
        png = SimpleUploadedFile("receipt.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        form = TravelBookingForm(_travel_booking_payload(), {"document": png}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_exe_document_rejected(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm
        exe_file = SimpleUploadedFile("malware.exe", b"MZ\x90\x00", content_type="application/octet-stream")
        form = TravelBookingForm(_travel_booking_payload(), {"document": exe_file}, tenant=tenant_a)
        assert not form.is_valid()
        assert "document" in form.errors

    def test_oversized_document_rejected(self, tenant_a):
        from apps.hrm.forms import TravelBookingForm, MAX_ONBOARDING_DOC_BYTES
        big_file = SimpleUploadedFile(
            "huge.pdf", b"A" * (MAX_ONBOARDING_DOC_BYTES + 1), content_type="application/pdf")
        form = TravelBookingForm(_travel_booking_payload(), {"document": big_file}, tenant=tenant_a)
        assert not form.is_valid()
        assert "document" in form.errors

    def test_tenant_and_travel_request_not_fields(self):
        from apps.hrm.forms import TravelBookingForm
        assert "tenant" not in TravelBookingForm.Meta.fields
        assert "travel_request" not in TravelBookingForm.Meta.fields


# ============================================================
# 5. TravelPolicy CRUD + access control
# ============================================================

class TestTravelPolicyListView:
    def test_200(self, client_a, travel_policy_a):
        resp = client_a.get(reverse("hrm:travelpolicy_list"))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/travel/travelpolicy/list.html"

    def test_context_keys(self, client_a, travel_policy_a):
        resp = client_a.get(reverse("hrm:travelpolicy_list"))
        for key in ("object_list", "page_obj", "q", "is_admin", "job_grades"):
            assert key in resp.context

    def test_search_by_name(self, client_a, travel_policy_a):
        resp = client_a.get(reverse("hrm:travelpolicy_list"), {"q": "Standard"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert travel_policy_a.pk in pks

    def test_filter_by_is_active(self, client_a, travel_policy_a, tenant_a):
        from apps.hrm.models import TravelPolicy
        inactive = TravelPolicy.objects.create(tenant=tenant_a, name="Inactive", is_active=False)
        resp = client_a.get(reverse("hrm:travelpolicy_list"), {"is_active": "False"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert inactive.pk in pks
        assert travel_policy_a.pk not in pks

    def test_bad_page_no_500(self, client_a, travel_policy_a):
        resp = client_a.get(reverse("hrm:travelpolicy_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_non_admin_can_view(self, member_client, travel_policy_a):
        resp = member_client.get(reverse("hrm:travelpolicy_list"))
        assert resp.status_code == 200


class TestTravelPolicyCreateView:
    def test_admin_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:travelpolicy_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_admin_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import TravelPolicy
        resp = client_a.post(reverse("hrm:travelpolicy_create"), _travel_policy_payload(name="Deluxe"))
        assert resp.status_code == 302
        obj = TravelPolicy.objects.get(tenant=tenant_a, name="Deluxe")
        assert obj.tenant_id == tenant_a.pk

    def test_non_admin_forbidden(self, member_client):
        resp = member_client.get(reverse("hrm:travelpolicy_create"))
        assert resp.status_code == 403

    def test_anonymous_redirected(self, client):
        resp = client.get(reverse("hrm:travelpolicy_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestTravelPolicyDetailView:
    def test_200_with_request_count(self, client_a, travel_policy_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelpolicy_detail", args=[travel_policy_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == travel_policy_a.pk
        assert resp.context["request_count"] == 1


class TestTravelPolicyEditView:
    def test_admin_get_200(self, client_a, travel_policy_a):
        resp = client_a.get(reverse("hrm:travelpolicy_edit", args=[travel_policy_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_admin_post_updates(self, client_a, travel_policy_a):
        resp = client_a.post(reverse("hrm:travelpolicy_edit", args=[travel_policy_a.pk]),
                              _travel_policy_payload(name="Renamed Policy"))
        assert resp.status_code == 302
        travel_policy_a.refresh_from_db()
        assert travel_policy_a.name == "Renamed Policy"

    def test_non_admin_forbidden(self, member_client, travel_policy_a):
        resp = member_client.post(reverse("hrm:travelpolicy_edit", args=[travel_policy_a.pk]),
                                   _travel_policy_payload(name="Hacked"))
        assert resp.status_code == 403
        travel_policy_a.refresh_from_db()
        assert travel_policy_a.name != "Hacked"


class TestTravelPolicyDeleteView:
    def test_get_not_allowed(self, client_a, travel_policy_a):
        resp = client_a.get(reverse("hrm:travelpolicy_delete", args=[travel_policy_a.pk]))
        assert resp.status_code == 405

    def test_deletes_unreferenced_policy(self, client_a, tenant_a):
        from apps.hrm.models import TravelPolicy
        policy = TravelPolicy.objects.create(tenant=tenant_a, name="Unreferenced")
        resp = client_a.post(reverse("hrm:travelpolicy_delete", args=[policy.pk]))
        assert resp.status_code == 302
        assert not TravelPolicy.objects.filter(pk=policy.pk).exists()

    def test_blocks_delete_of_referenced_policy(self, client_a, travel_policy_a, draft_trip_a):
        from apps.hrm.models import TravelPolicy
        resp = client_a.post(reverse("hrm:travelpolicy_delete", args=[travel_policy_a.pk]))
        assert resp.status_code == 302
        assert TravelPolicy.objects.filter(pk=travel_policy_a.pk).exists()

    def test_non_admin_forbidden(self, member_client, tenant_a):
        from apps.hrm.models import TravelPolicy
        policy = TravelPolicy.objects.create(tenant=tenant_a, name="Guarded")
        resp = member_client.post(reverse("hrm:travelpolicy_delete", args=[policy.pk]))
        assert resp.status_code == 403
        assert TravelPolicy.objects.filter(pk=policy.pk).exists()

    def test_enforces_csrf(self, admin_user, tenant_a):
        from apps.hrm.models import TravelPolicy
        policy = TravelPolicy.objects.create(tenant=tenant_a, name="CSRF Guarded")
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:travelpolicy_delete", args=[policy.pk]))
        assert resp.status_code == 403
        assert TravelPolicy.objects.filter(pk=policy.pk).exists()


# ============================================================
# 6. TravelRequest CRUD + own-vs-admin scoping
# ============================================================

class TestTravelRequestListView:
    def test_200(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/travel/travelrequest/list.html"

    def test_context_keys(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"))
        for key in ("object_list", "page_obj", "q", "status_choices", "trip_type_choices",
                    "is_admin", "employees"):
            assert key in resp.context

    def test_search_by_title(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"), {"q": "Client Site"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk in pks

    def test_search_by_number(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"), {"q": draft_trip_a.number})
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk in pks

    def test_filter_by_status(self, client_a, draft_trip_a, pending_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"), {"status": "pending"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert pending_trip_a.pk in pks

    def test_filter_by_trip_type(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"), {"trip_type": "domestic"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk in pks

    def test_bad_page_no_500(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_non_admin_can_view(self, member_client):
        resp = member_client.get(reverse("hrm:travelrequest_list"))
        assert resp.status_code == 200


class TestOwnVsAdminScoping:
    def test_own_client_sees_only_own_trips(self, own_client, draft_trip_a, tenant_a, employee_a2):
        from apps.hrm.models import TravelRequest
        other_trip = TravelRequest.objects.create(
            tenant=tenant_a, employee=employee_a2, title="Not Mine", origin="X", destination="Y",
            purpose="Z", start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 2))
        resp = own_client.get(reverse("hrm:travelrequest_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk in pks
        assert other_trip.pk not in pks

    def test_other_employee_client_cannot_see_draft_trip_a(self, other_employee_client, draft_trip_a):
        resp = other_employee_client.get(reverse("hrm:travelrequest_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk not in pks

    def test_other_employee_client_detail_403(self, other_employee_client, draft_trip_a):
        resp = other_employee_client.get(reverse("hrm:travelrequest_detail", args=[draft_trip_a.pk]))
        assert resp.status_code == 403

    def test_admin_sees_all_trips(self, client_a, draft_trip_a, tenant_a, employee_a2):
        from apps.hrm.models import TravelRequest
        other_trip = TravelRequest.objects.create(
            tenant=tenant_a, employee=employee_a2, title="Someone Else's", origin="X", destination="Y",
            purpose="Z", start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 2))
        resp = client_a.get(reverse("hrm:travelrequest_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk in pks
        assert other_trip.pk in pks

    def test_admin_can_view_any_trip(self, client_a, draft_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_detail", args=[draft_trip_a.pk]))
        assert resp.status_code == 200

    def test_employee_less_non_admin_sees_no_trips(self, member_client, draft_trip_a):
        resp = member_client.get(reverse("hrm:travelrequest_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_trip_a.pk not in pks

    def test_employee_less_non_admin_detail_403(self, member_client, draft_trip_a):
        resp = member_client.get(reverse("hrm:travelrequest_detail", args=[draft_trip_a.pk]))
        assert resp.status_code == 403


class TestTravelRequestCreateView:
    def test_owner_get_200(self, own_client):
        resp = own_client.get(reverse("hrm:travelrequest_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_owner_post_creates_for_self(self, own_client, tenant_a, employee_a):
        from apps.hrm.models import TravelRequest
        resp = own_client.post(reverse("hrm:travelrequest_create"),
                                _travel_request_payload(title="My Own Trip"))
        assert resp.status_code == 302
        obj = TravelRequest.objects.get(tenant=tenant_a, title="My Own Trip")
        assert obj.employee_id == employee_a.pk
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("TRV-")

    def test_admin_post_with_employee_pk_creates_for_target(self, client_a, tenant_a, employee_a2):
        from apps.hrm.models import TravelRequest
        resp = client_a.post(reverse("hrm:travelrequest_create"),
                              _travel_request_payload(title="Admin Assigned Trip",
                                                       employee_pk=str(employee_a2.pk)))
        assert resp.status_code == 302
        obj = TravelRequest.objects.get(tenant=tenant_a, title="Admin Assigned Trip")
        assert obj.employee_id == employee_a2.pk

    def test_invalid_payload_rerenders_form(self, own_client):
        resp = own_client.post(
            reverse("hrm:travelrequest_create"),
            _travel_request_payload(start_date="2026-08-10", end_date="2026-08-01"))
        assert resp.status_code == 200
        assert resp.context["form"].errors


class TestTravelRequestDetailView:
    def test_200_with_context(self, client_a, draft_trip_a, booking_a):
        from apps.hrm.models import TravelBooking
        resp = client_a.get(reverse("hrm:travelrequest_detail", args=[draft_trip_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == draft_trip_a.pk
        assert [b.pk for b in resp.context["bookings"]] == [booking_a.pk]
        assert resp.context["is_admin"] is True
        assert resp.context["booking_form"] is not None
        assert resp.context["booking_type_choices"] == TravelBooking.BOOKING_TYPE_CHOICES
        assert resp.context["net_settlement"] is None

    def test_booking_form_none_when_not_open(self, client_a, approved_trip_a):
        resp = client_a.get(reverse("hrm:travelrequest_detail", args=[approved_trip_a.pk]))
        assert resp.context["booking_form"] is None


# ============================================================
# 7. Full single-approver workflow + OPEN_STATUSES edit/delete gate
# ============================================================

class TestFullWorkflow:
    def test_create_submit_approve_complete(self, own_client, client_a, tenant_a, employee_a, admin_user):
        from apps.hrm.models import TravelRequest
        # 1. create (draft)
        resp = own_client.post(reverse("hrm:travelrequest_create"),
                                _travel_request_payload(title="Full Workflow Trip"))
        assert resp.status_code == 302
        trip = TravelRequest.objects.get(tenant=tenant_a, title="Full Workflow Trip")
        assert trip.status == "draft"

        # 2. submit (pending) — still OPEN, edit/delete still allowed
        resp = own_client.post(reverse("hrm:travelrequest_submit", args=[trip.pk]))
        assert resp.status_code == 302
        trip.refresh_from_db()
        assert trip.status == "pending"
        resp = own_client.post(reverse("hrm:travelrequest_edit", args=[trip.pk]),
                                _travel_request_payload(title="Still Editable"))
        assert resp.status_code == 302
        trip.refresh_from_db()
        assert trip.title == "Still Editable"

        # 3. approve (approved, approver stamped by a DIFFERENT admin) — no longer OPEN
        resp = client_a.post(reverse("hrm:travelrequest_approve", args=[trip.pk]))
        assert resp.status_code == 302
        trip.refresh_from_db()
        assert trip.status == "approved"
        assert trip.approver_id == admin_user.pk
        assert trip.approved_at is not None

        # edit/delete blocked now that the trip left OPEN_STATUSES
        resp = own_client.post(reverse("hrm:travelrequest_edit", args=[trip.pk]),
                                _travel_request_payload(title="Hacked After Approval"))
        assert resp.status_code == 302
        trip.refresh_from_db()
        assert trip.title != "Hacked After Approval"
        resp = own_client.post(reverse("hrm:travelrequest_delete", args=[trip.pk]))
        assert resp.status_code == 302
        assert TravelRequest.objects.filter(pk=trip.pk).exists()

        # 4. complete (completed)
        resp = own_client.post(reverse("hrm:travelrequest_complete", args=[trip.pk]))
        assert resp.status_code == 302
        trip.refresh_from_db()
        assert trip.status == "completed"

    def test_reject_from_pending_stamps_approver_and_decision_note(self, client_a, pending_trip_a, admin_user):
        resp = client_a.post(reverse("hrm:travelrequest_reject", args=[pending_trip_a.pk]),
                              {"decision_note": "Budget not approved"})
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "rejected"
        assert pending_trip_a.approver_id == admin_user.pk
        assert pending_trip_a.approved_at is not None
        assert pending_trip_a.decision_note == "Budget not approved"

    def test_reject_missing_reason_rejected(self, client_a, pending_trip_a):
        resp = client_a.post(reverse("hrm:travelrequest_reject", args=[pending_trip_a.pk]), {})
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "pending"

    def test_approve_from_draft_rejected(self, client_a, draft_trip_a):
        resp = client_a.post(reverse("hrm:travelrequest_approve", args=[draft_trip_a.pk]))
        assert resp.status_code == 302
        draft_trip_a.refresh_from_db()
        assert draft_trip_a.status == "draft"

    def test_cancel_from_draft(self, own_client, draft_trip_a):
        resp = own_client.post(reverse("hrm:travelrequest_cancel", args=[draft_trip_a.pk]))
        assert resp.status_code == 302
        draft_trip_a.refresh_from_db()
        assert draft_trip_a.status == "cancelled"

    def test_cancel_from_approved_rejected(self, own_client, approved_trip_a):
        resp = own_client.post(reverse("hrm:travelrequest_cancel", args=[approved_trip_a.pk]))
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.status == "approved"

    def test_complete_from_pending_rejected(self, own_client, pending_trip_a):
        resp = own_client.post(reverse("hrm:travelrequest_complete", args=[pending_trip_a.pk]))
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "pending"

    def test_edit_non_owner_redirects_to_detail(self, other_employee_client, draft_trip_a):
        """Ownership is checked BEFORE the open-status branch (_hr_request_edit) — a non-owner gets
        a redirect to detail (NOT a 403, since _hr_request_edit is shared 3.26 machinery)."""
        resp = other_employee_client.post(reverse("hrm:travelrequest_edit", args=[draft_trip_a.pk]),
                                           _travel_request_payload(title="Hacked"))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:travelrequest_detail", args=[draft_trip_a.pk])
        draft_trip_a.refresh_from_db()
        assert draft_trip_a.title != "Hacked"

    def test_delete_non_owner_row_survives(self, other_employee_client, draft_trip_a):
        from apps.hrm.models import TravelRequest
        resp = other_employee_client.post(reverse("hrm:travelrequest_delete", args=[draft_trip_a.pk]))
        assert resp.status_code == 302
        assert TravelRequest.objects.filter(pk=draft_trip_a.pk).exists()


# ============================================================
# 8. approve_advance
# ============================================================

class TestApproveAdvance:
    def test_no_advance_requested_rejected(self, client_a, approved_trip_no_advance_requested_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_no_advance_requested_a.pk]),
            {"advance_approved": "100.00"})
        assert resp.status_code == 302
        approved_trip_no_advance_requested_a.refresh_from_db()
        assert approved_trip_no_advance_requested_a.advance_approved is None

    def test_percent_cap_boundary_accepted(self, client_a, approved_trip_with_cap_a):
        """cap = 80% of 1000 = 800.00 — amount == cap is accepted."""
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_with_cap_a.pk]),
            {"advance_approved": "800.00"})
        assert resp.status_code == 302
        approved_trip_with_cap_a.refresh_from_db()
        assert approved_trip_with_cap_a.advance_approved == Decimal("800.00")

    def test_percent_cap_boundary_plus_one_cent_rejected(self, client_a, approved_trip_with_cap_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_with_cap_a.pk]),
            {"advance_approved": "800.01"})
        assert resp.status_code == 302
        approved_trip_with_cap_a.refresh_from_db()
        assert approved_trip_with_cap_a.advance_approved is None

    def test_amount_over_advance_requested_rejected(self, client_a, approved_trip_a):
        """advance_requested=500 — amount=600 exceeds it (isolated from the policy % cap, which
        checks AFTER the requested-amount ceiling)."""
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "600.00"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_amount_equal_advance_requested_within_cap_accepted(self, client_a, approved_trip_a):
        """advance_requested=500, policy cap=800 — 500 is within both -> accepted."""
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "500.00"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved == Decimal("500.00")

    def test_negative_amount_rejected(self, client_a, approved_trip_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "-10"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_nan_does_not_500(self, client_a, approved_trip_a):
        """WARNING guard: Decimal('nan') parses without raising but is non-finite — the view must
        reject it via .is_finite() rather than crash on a later ordering comparison."""
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "nan"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_infinity_does_not_500(self, client_a, approved_trip_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "inf"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_garbage_input_does_not_500(self, client_a, approved_trip_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "not-a-number"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_amount_at_or_over_ten_billion_rejected(self, client_a, approved_trip_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "10000000000"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_not_approved_trip_rejected(self, client_a, pending_trip_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[pending_trip_a.pk]),
            {"advance_approved": "100.00"})
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.advance_approved is None

    def test_non_admin_forbidden(self, member_client, approved_trip_a):
        resp = member_client.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "100.00"})
        assert resp.status_code == 403


# ============================================================
# 9. mark_advance_paid
# ============================================================

class TestMarkAdvancePaid:
    def test_requires_approved_advance(self, client_a, approved_trip_a):
        """advance_approved is None -> rejected."""
        resp = client_a.post(reverse("hrm:travelrequest_mark_advance_paid", args=[approved_trip_a.pk]),
                              {"advance_reference": "WIRE001"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_paid_at is None

    def test_success(self, client_a, approved_trip_with_paid_advance_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_mark_advance_paid", args=[approved_trip_with_paid_advance_a.pk]),
            {"advance_reference": "WIRE002"})
        assert resp.status_code == 302
        approved_trip_with_paid_advance_a.refresh_from_db()
        assert approved_trip_with_paid_advance_a.advance_paid_at is not None
        assert approved_trip_with_paid_advance_a.advance_reference == "WIRE002"

    def test_idempotent_second_call_is_noop(self, client_a, approved_trip_with_paid_advance_a):
        client_a.post(
            reverse("hrm:travelrequest_mark_advance_paid", args=[approved_trip_with_paid_advance_a.pk]),
            {"advance_reference": "WIRE003"})
        approved_trip_with_paid_advance_a.refresh_from_db()
        first_paid_at = approved_trip_with_paid_advance_a.advance_paid_at
        assert first_paid_at is not None
        resp = client_a.post(
            reverse("hrm:travelrequest_mark_advance_paid", args=[approved_trip_with_paid_advance_a.pk]),
            {"advance_reference": "WIRE_DIFFERENT"})
        assert resp.status_code == 302
        approved_trip_with_paid_advance_a.refresh_from_db()
        assert approved_trip_with_paid_advance_a.advance_paid_at == first_paid_at
        assert approved_trip_with_paid_advance_a.advance_reference == "WIRE003"

    def test_non_admin_forbidden(self, member_client, approved_trip_with_paid_advance_a):
        resp = member_client.post(
            reverse("hrm:travelrequest_mark_advance_paid", args=[approved_trip_with_paid_advance_a.pk]), {})
        assert resp.status_code == 403


# ============================================================
# 10. generate_settlement
# ============================================================

class TestGenerateSettlement:
    def test_success_creates_linked_draft_claim(self, own_client, tenant_a, approved_trip_a):
        resp = own_client.post(
            reverse("hrm:travelrequest_generate_settlement", args=[approved_trip_a.pk]))
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.settlement_claim_id is not None
        claim = approved_trip_a.settlement_claim
        assert claim.employee_id == approved_trip_a.employee_id
        assert claim.status == "draft"
        assert claim.tenant_id == tenant_a.pk

    def test_idempotent_second_call_creates_no_second_claim(self, own_client, tenant_a, approved_trip_a):
        from apps.hrm.models import ExpenseClaim
        own_client.post(reverse("hrm:travelrequest_generate_settlement", args=[approved_trip_a.pk]))
        approved_trip_a.refresh_from_db()
        first_claim_id = approved_trip_a.settlement_claim_id
        before = ExpenseClaim.objects.filter(tenant=tenant_a).count()
        resp = own_client.post(
            reverse("hrm:travelrequest_generate_settlement", args=[approved_trip_a.pk]))
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.settlement_claim_id == first_claim_id
        assert ExpenseClaim.objects.filter(tenant=tenant_a).count() == before

    def test_blocked_before_approved(self, own_client, pending_trip_a):
        resp = own_client.post(
            reverse("hrm:travelrequest_generate_settlement", args=[pending_trip_a.pk]))
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.settlement_claim_id is None

    def test_non_owner_non_admin_forbidden(self, other_employee_client, approved_trip_a):
        resp = other_employee_client.post(
            reverse("hrm:travelrequest_generate_settlement", args=[approved_trip_a.pk]))
        assert resp.status_code == 403


# ============================================================
# 11. Inline TravelBooking CRUD
# ============================================================

class TestTravelBookingCRUD:
    def test_add_booking_success(self, own_client, draft_trip_a):
        from apps.hrm.models import TravelBooking
        resp = own_client.post(reverse("hrm:travelbooking_add", args=[draft_trip_a.pk]),
                                _travel_booking_payload())
        assert resp.status_code == 302
        assert TravelBooking.objects.filter(travel_request=draft_trip_a).count() == 1

    def test_add_booking_with_document_attaches(self, own_client, draft_trip_a):
        from apps.hrm.models import TravelBooking
        pdf = SimpleUploadedFile("itinerary.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        resp = own_client.post(reverse("hrm:travelbooking_add", args=[draft_trip_a.pk]),
                                {**_travel_booking_payload(), "document": pdf})
        assert resp.status_code == 302
        booking = TravelBooking.objects.get(travel_request=draft_trip_a)
        assert booking.document.name

    def test_add_booking_invalid_payload_creates_nothing(self, own_client, draft_trip_a):
        from apps.hrm.models import TravelBooking
        resp = own_client.post(reverse("hrm:travelbooking_add", args=[draft_trip_a.pk]),
                                _travel_booking_payload(cost="-5"))
        assert resp.status_code == 302
        assert not TravelBooking.objects.filter(travel_request=draft_trip_a).exists()

    def test_add_booking_blocked_when_not_open(self, own_client, approved_trip_a):
        from apps.hrm.models import TravelBooking
        resp = own_client.post(reverse("hrm:travelbooking_add", args=[approved_trip_a.pk]),
                                _travel_booking_payload())
        assert resp.status_code == 302
        assert not TravelBooking.objects.filter(travel_request=approved_trip_a).exists()

    def test_add_booking_by_non_owner_forbidden(self, other_employee_client, draft_trip_a):
        resp = other_employee_client.post(reverse("hrm:travelbooking_add", args=[draft_trip_a.pk]),
                                           _travel_booking_payload())
        assert resp.status_code == 403

    def test_edit_booking_get_200(self, client_a, booking_a):
        resp = client_a.get(reverse("hrm:travelbooking_edit", args=[booking_a.pk]))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/travel/travelbooking/form.html"
        assert resp.context["is_edit"] is True

    def test_edit_booking_post_updates(self, client_a, booking_a):
        resp = client_a.post(reverse("hrm:travelbooking_edit", args=[booking_a.pk]),
                              _travel_booking_payload(vendor="United Airlines"))
        assert resp.status_code == 302
        booking_a.refresh_from_db()
        assert booking_a.vendor == "United Airlines"

    def test_edit_booking_blocked_when_not_open(self, client_a, booking_on_approved_a):
        resp = client_a.post(reverse("hrm:travelbooking_edit", args=[booking_on_approved_a.pk]),
                              _travel_booking_payload(vendor="Hacked Vendor"))
        assert resp.status_code == 302
        booking_on_approved_a.refresh_from_db()
        assert booking_on_approved_a.vendor != "Hacked Vendor"

    def test_edit_booking_by_non_owner_forbidden(self, other_employee_client, booking_a):
        resp = other_employee_client.get(reverse("hrm:travelbooking_edit", args=[booking_a.pk]))
        assert resp.status_code == 403

    def test_delete_booking_success(self, client_a, booking_a):
        from apps.hrm.models import TravelBooking
        pk = booking_a.pk
        resp = client_a.post(reverse("hrm:travelbooking_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TravelBooking.objects.filter(pk=pk).exists()

    def test_delete_booking_get_not_allowed(self, client_a, booking_a):
        resp = client_a.get(reverse("hrm:travelbooking_delete", args=[booking_a.pk]))
        assert resp.status_code == 405

    def test_delete_booking_blocked_when_not_open(self, client_a, booking_on_approved_a):
        from apps.hrm.models import TravelBooking
        resp = client_a.post(reverse("hrm:travelbooking_delete", args=[booking_on_approved_a.pk]))
        assert resp.status_code == 302
        assert TravelBooking.objects.filter(pk=booking_on_approved_a.pk).exists()

    def test_delete_booking_by_non_owner_forbidden(self, other_employee_client, booking_a):
        from apps.hrm.models import TravelBooking
        resp = other_employee_client.post(reverse("hrm:travelbooking_delete", args=[booking_a.pk]))
        assert resp.status_code == 403
        assert TravelBooking.objects.filter(pk=booking_a.pk).exists()


# ============================================================
# 12. Self-approval / maker-checker block
# ============================================================

class TestSelfApprovalBlock:
    def test_approve_own_trip_blocked(self, self_admin_client, pending_trip_a):
        resp = self_admin_client.post(reverse("hrm:travelrequest_approve", args=[pending_trip_a.pk]))
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "pending"
        assert pending_trip_a.approver_id is None

    def test_approve_different_admin_allowed(self, client_a, pending_trip_a, admin_user):
        resp = client_a.post(reverse("hrm:travelrequest_approve", args=[pending_trip_a.pk]))
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "approved"
        assert pending_trip_a.approver_id == admin_user.pk

    def test_reject_own_trip_blocked(self, self_admin_client, pending_trip_a):
        resp = self_admin_client.post(reverse("hrm:travelrequest_reject", args=[pending_trip_a.pk]),
                                       {"decision_note": "self trying to reject"})
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "pending"

    def test_reject_different_admin_allowed(self, client_a, pending_trip_a):
        resp = client_a.post(reverse("hrm:travelrequest_reject", args=[pending_trip_a.pk]),
                              {"decision_note": "Not viable"})
        assert resp.status_code == 302
        pending_trip_a.refresh_from_db()
        assert pending_trip_a.status == "rejected"

    def test_approve_advance_own_blocked(self, self_admin_client, approved_trip_a):
        resp = self_admin_client.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "500.00"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None

    def test_approve_advance_different_admin_allowed(self, client_a, approved_trip_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "500.00"})
        assert resp.status_code == 302
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved == Decimal("500.00")

    def test_mark_advance_paid_own_blocked(self, self_admin_client, approved_trip_with_paid_advance_a):
        resp = self_admin_client.post(
            reverse("hrm:travelrequest_mark_advance_paid",
                    args=[approved_trip_with_paid_advance_a.pk]), {})
        assert resp.status_code == 302
        approved_trip_with_paid_advance_a.refresh_from_db()
        assert approved_trip_with_paid_advance_a.advance_paid_at is None

    def test_mark_advance_paid_different_admin_allowed(self, client_a, approved_trip_with_paid_advance_a):
        resp = client_a.post(
            reverse("hrm:travelrequest_mark_advance_paid",
                    args=[approved_trip_with_paid_advance_a.pk]), {})
        assert resp.status_code == 302
        approved_trip_with_paid_advance_a.refresh_from_db()
        assert approved_trip_with_paid_advance_a.advance_paid_at is not None


# ============================================================
# 13. Multi-tenant isolation / IDOR
# ============================================================

class TestMultiTenantIsolation:
    def test_travelpolicy_detail_404_cross_tenant(self, client_a, travel_policy_b):
        resp = client_a.get(reverse("hrm:travelpolicy_detail", args=[travel_policy_b.pk]))
        assert resp.status_code == 404

    def test_travelpolicy_edit_404_cross_tenant(self, client_a, travel_policy_b):
        resp = client_a.get(reverse("hrm:travelpolicy_edit", args=[travel_policy_b.pk]))
        assert resp.status_code == 404

    def test_travelpolicy_delete_404_cross_tenant(self, client_a, travel_policy_b):
        from apps.hrm.models import TravelPolicy
        resp = client_a.post(reverse("hrm:travelpolicy_delete", args=[travel_policy_b.pk]))
        assert resp.status_code == 404
        assert TravelPolicy.objects.filter(pk=travel_policy_b.pk).exists()

    def test_travelpolicy_list_excludes_other_tenant(self, client_a, travel_policy_b):
        resp = client_a.get(reverse("hrm:travelpolicy_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert travel_policy_b.pk not in pks

    def test_travelrequest_detail_404_cross_tenant(self, client_a, trip_b):
        resp = client_a.get(reverse("hrm:travelrequest_detail", args=[trip_b.pk]))
        assert resp.status_code == 404

    def test_travelrequest_edit_404_cross_tenant(self, client_a, trip_b):
        resp = client_a.get(reverse("hrm:travelrequest_edit", args=[trip_b.pk]))
        assert resp.status_code == 404

    def test_travelrequest_delete_404_cross_tenant(self, client_a, trip_b):
        from apps.hrm.models import TravelRequest
        resp = client_a.post(reverse("hrm:travelrequest_delete", args=[trip_b.pk]))
        assert resp.status_code == 404
        assert TravelRequest.objects.filter(pk=trip_b.pk).exists()

    @pytest.mark.parametrize("url_name", [
        "travelrequest_submit", "travelrequest_approve", "travelrequest_reject",
        "travelrequest_cancel", "travelrequest_complete", "travelrequest_generate_settlement",
    ])
    def test_travelrequest_workflow_actions_404_cross_tenant(self, client_a, trip_b, url_name):
        resp = client_a.post(reverse(f"hrm:{url_name}", args=[trip_b.pk]))
        assert resp.status_code == 404

    @pytest.mark.parametrize("url_name", [
        "travelrequest_approve_advance", "travelrequest_mark_advance_paid",
    ])
    def test_travelrequest_advance_actions_404_cross_tenant(self, client_a, trip_b, url_name):
        resp = client_a.post(reverse(f"hrm:{url_name}", args=[trip_b.pk]), {"advance_approved": "10"})
        assert resp.status_code == 404

    def test_travelrequest_list_excludes_other_tenant(self, client_a, trip_b):
        resp = client_a.get(reverse("hrm:travelrequest_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert trip_b.pk not in pks

    def test_travelbooking_edit_404_cross_tenant(self, client_a, booking_b):
        resp = client_a.get(reverse("hrm:travelbooking_edit", args=[booking_b.pk]))
        assert resp.status_code == 404

    def test_travelbooking_delete_404_cross_tenant(self, client_a, booking_b):
        from apps.hrm.models import TravelBooking
        resp = client_a.post(reverse("hrm:travelbooking_delete", args=[booking_b.pk]))
        assert resp.status_code == 404
        assert TravelBooking.objects.filter(pk=booking_b.pk).exists()

    def test_travelbooking_add_404_cross_tenant_trip(self, client_a, trip_b):
        resp = client_a.post(reverse("hrm:travelbooking_add", args=[trip_b.pk]),
                              _travel_booking_payload())
        assert resp.status_code == 404


# ============================================================
# 14. Authorization (non-admin 403 on admin-only actions)
# ============================================================

class TestAuthorization:
    @pytest.mark.parametrize("url_name", ["travelpolicy_create"])
    def test_non_admin_403_get(self, member_client, url_name):
        resp = member_client.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 403

    def test_non_admin_403_travelpolicy_edit(self, member_client, travel_policy_a):
        resp = member_client.get(reverse("hrm:travelpolicy_edit", args=[travel_policy_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_travelpolicy_delete(self, member_client, travel_policy_a):
        resp = member_client.post(reverse("hrm:travelpolicy_delete", args=[travel_policy_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_travelrequest_approve(self, member_client, pending_trip_a):
        resp = member_client.post(reverse("hrm:travelrequest_approve", args=[pending_trip_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_travelrequest_reject(self, member_client, pending_trip_a):
        resp = member_client.post(reverse("hrm:travelrequest_reject", args=[pending_trip_a.pk]),
                                   {"decision_note": "no"})
        assert resp.status_code == 403

    def test_non_admin_403_travelrequest_approve_advance(self, member_client, approved_trip_a):
        resp = member_client.post(
            reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
            {"advance_approved": "100"})
        assert resp.status_code == 403

    def test_non_admin_403_travelrequest_mark_advance_paid(
            self, member_client, approved_trip_with_paid_advance_a):
        resp = member_client.post(
            reverse("hrm:travelrequest_mark_advance_paid",
                    args=[approved_trip_with_paid_advance_a.pk]), {})
        assert resp.status_code == 403


# ============================================================
# 15. Anonymous access
# ============================================================

class TestAnonymousAccess:
    @pytest.mark.parametrize("url_name", [
        "hrm:travelpolicy_list", "hrm:travelpolicy_create",
        "hrm:travelrequest_list", "hrm:travelrequest_create",
    ])
    def test_anon_redirected(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_and_edit(self, client, draft_trip_a, travel_policy_a):
        for url_name, pk in [
            ("hrm:travelpolicy_detail", travel_policy_a.pk),
            ("hrm:travelpolicy_edit", travel_policy_a.pk),
            ("hrm:travelrequest_detail", draft_trip_a.pk),
            ("hrm:travelrequest_edit", draft_trip_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only(self, client, draft_trip_a, travel_policy_a):
        for url_name, pk in [
            ("hrm:travelpolicy_delete", travel_policy_a.pk),
            ("hrm:travelrequest_delete", draft_trip_a.pk),
            ("hrm:travelrequest_submit", draft_trip_a.pk),
            ("hrm:travelrequest_cancel", draft_trip_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ============================================================
# 16. CSRF enforcement
# ============================================================

class TestCSRFEnforcement:
    def test_travelbooking_delete_enforces_csrf(self, admin_user, booking_a):
        from apps.hrm.models import TravelBooking
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:travelbooking_delete", args=[booking_a.pk]))
        assert resp.status_code == 403
        assert TravelBooking.objects.filter(pk=booking_a.pk).exists()

    def test_travelrequest_approve_advance_enforces_csrf(self, admin_user, approved_trip_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:travelrequest_approve_advance", args=[approved_trip_a.pk]),
                       {"advance_approved": "500.00"})
        assert resp.status_code == 403
        approved_trip_a.refresh_from_db()
        assert approved_trip_a.advance_approved is None


# ============================================================
# 17. Query-count ceiling (N+1 guard)
# ============================================================

class TestTravelRequestListQueryCount:
    def test_query_count_bounded(self, client_a, many_travel_requests_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:travelrequest_list"))

    def test_query_count_does_not_grow_with_trip_count(self, client_a, tenant_a, employee_a):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        from apps.hrm.models import TravelRequest

        def _make_trips(n, start):
            for i in range(start, start + n):
                TravelRequest.objects.create(
                    tenant=tenant_a, employee=employee_a, title=f"T{i}", origin="NYC",
                    destination="LA", purpose="Bulk",
                    start_date=datetime.date(2026, 8, 1), end_date=datetime.date(2026, 8, 2))

        _make_trips(2, 0)
        with CaptureQueriesContext(connection) as small_ctx:
            resp = client_a.get(reverse("hrm:travelrequest_list"))
        assert resp.status_code == 200
        small_count = len(small_ctx.captured_queries)

        _make_trips(10, 2)
        with CaptureQueriesContext(connection) as large_ctx:
            resp = client_a.get(reverse("hrm:travelrequest_list"))
        assert resp.status_code == 200
        large_count = len(large_ctx.captured_queries)

        assert large_count == small_count
