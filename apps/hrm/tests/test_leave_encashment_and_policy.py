"""Comprehensive tests for the HRM 3.10 Leave Management **completion** — the
``LeaveEncashment`` model + workflow, the Leave Policy engine (``leave_accrual_run`` /
``leave_carryforward_run``), and the ``LeaveAllocation.carried_forward`` / ``encashed_days``
fields added to support it.

Covers:
  - LeaveEncashment model: save() computes amount = days x rate_per_day; clean() guards
    (days <= 0, non-encashable leave_type, days > available balance); ENC- per-tenant
    numbering isolated across tenants.
  - LeaveEncashment workflow via the test client: submit / approve (+ LeaveAllocation.
    encashed_days increment, allocated_days unchanged) / mark_paid / reject / cancel;
    edit/delete guards on decided rows; approve re-checks balance and blocks a second
    over-balance approval; @tenant_admin_required 403 for a non-admin.
  - Leave Policy engine: leave_accrual_run (annual/monthly/future-year/cap/idempotency),
    leave_carryforward_run (dest allocated_days/carried_forward, cap, idempotency), the
    double-spend regression (accrual re-run must not restore encashed days), carry-forward
    netting encashed days, _policy_year bounds, and single-tenant blast radius.
  - Forms: LeaveEncashmentForm excludes workflow/derived fields and narrows leave_type to
    encashable types; LeaveAllocationForm resets carried_forward on a manual allocated_days
    edit.
  - Offboarding integration: compute_leave_encashment nets out already-encashed days.
  - Multi-tenant IDOR sweep across every leaveencashment_* child-pk action.
  - Performance guards on leaveencashment_list and leaveallocation_detail.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Local fixtures
# ============================================================

@pytest.fixture
def non_encashable_type_a(db, tenant_a):
    """A non-encashable leave type for tenant_a."""
    from apps.hrm.models import LeaveType
    return LeaveType.objects.create(
        tenant=tenant_a, name="Sick Leave", code="SL",
        is_paid=True, accrual_rule="none", encashable=False,
    )


@pytest.fixture
def draft_encashment_a(db, tenant_a, employee_a, leave_type_a, leave_allocation_a):
    """A draft LeaveEncashment for employee_a: 5 days at 100/day against a 21-day balance."""
    from apps.hrm.models import LeaveEncashment
    return LeaveEncashment.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        leave_type=leave_type_a,
        year=leave_allocation_a.year,
        days=Decimal("5"),
        rate_per_day=Decimal("100"),
        status="draft",
    )


@pytest.fixture
def pending_encashment_a(db, draft_encashment_a):
    """A pending LeaveEncashment for employee_a (submitted)."""
    draft_encashment_a.status = "pending"
    draft_encashment_a.save(update_fields=["status", "updated_at"])
    return draft_encashment_a


@pytest.fixture
def leave_type_b_encashable(db, tenant_b):
    """An encashable LeaveType for tenant_b."""
    from apps.hrm.models import LeaveType
    return LeaveType.objects.create(
        tenant=tenant_b, name="Annual Leave B", code="ALB",
        is_paid=True, accrual_rule="annual", accrual_days=Decimal("18"),
        max_balance=Decimal("30"), encashable=True,
    )


@pytest.fixture
def leave_allocation_b(db, tenant_b, employee_b, leave_type_b_encashable):
    """A leave allocation for employee_b/tenant_b, same year as leave_allocation_a (2026)."""
    from apps.hrm.models import LeaveAllocation
    return LeaveAllocation.objects.create(
        tenant=tenant_b, employee=employee_b, leave_type=leave_type_b_encashable,
        year=2026, allocated_days=Decimal("18"), status="active",
    )


@pytest.fixture
def encashment_b(db, tenant_b, employee_b, leave_type_b_encashable, leave_allocation_b):
    """A pending LeaveEncashment belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import LeaveEncashment
    return LeaveEncashment.objects.create(
        tenant=tenant_b, employee=employee_b, leave_type=leave_type_b_encashable,
        year=leave_allocation_b.year, days=Decimal("3"), rate_per_day=Decimal("50"),
        status="pending",
    )


# ============================================================
# LeaveEncashment model — save() / amount
# ============================================================
class TestLeaveEncashmentAmount:
    def test_amount_computed_on_save(self, draft_encashment_a):
        assert draft_encashment_a.amount == Decimal("500.00")

    def test_amount_recomputed_when_days_change(self, draft_encashment_a):
        draft_encashment_a.days = Decimal("10")
        draft_encashment_a.save()
        draft_encashment_a.refresh_from_db()
        assert draft_encashment_a.amount == Decimal("1000.00")

    def test_amount_not_settable_directly_is_overwritten(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("2"), rate_per_day=Decimal("100"),
            amount=Decimal("999999.00"),  # attempted hand-edit
        )
        enc.save()
        assert enc.amount == Decimal("200.00")

    def test_amount_zero_rate(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("2"), rate_per_day=Decimal("0"),
        )
        assert enc.amount == Decimal("0.00")


# ============================================================
# LeaveEncashment model — clean() guards
# ============================================================
class TestLeaveEncashmentClean:
    def test_rejects_zero_days(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("0"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError) as exc:
            enc.full_clean()
        assert "days" in exc.value.message_dict

    def test_rejects_negative_days(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("-3"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError) as exc:
            enc.full_clean()
        assert "days" in exc.value.message_dict

    def test_rejects_non_encashable_leave_type(self, tenant_a, employee_a, non_encashable_type_a):
        from apps.hrm.models import LeaveEncashment, LeaveAllocation
        LeaveAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=non_encashable_type_a,
            year=2026, allocated_days=Decimal("10"), status="active",
        )
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=non_encashable_type_a,
            year=2026, days=Decimal("2"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError) as exc:
            enc.full_clean()
        assert "leave_type" in exc.value.message_dict

    def test_rejects_days_exceeding_balance(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """leave_allocation_a: 21 allocated, 0 used, 0 encashed -> balance 21."""
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("22"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError) as exc:
            enc.full_clean()
        assert "days" in exc.value.message_dict

    def test_accepts_days_equal_to_balance(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("21"), rate_per_day=Decimal("100"),
        )
        enc.full_clean()  # must not raise

    def test_rejects_days_exceeding_balance_after_prior_usage(
            self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """balance nets out approved LeaveRequest days: 21 allocated - 15 used = 6 available."""
        from apps.hrm.models import LeaveEncashment, LeaveRequest
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 3, 1), end_date=datetime.date(2026, 3, 15),
            status="approved",
        )
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("7"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError):
            enc.full_clean()

    def test_rejects_days_exceeding_balance_after_prior_encashment(
            self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """balance nets out encashed_days too: 21 allocated - 10 encashed = 11 available."""
        from apps.hrm.models import LeaveEncashment
        leave_allocation_a.encashed_days = Decimal("10")
        leave_allocation_a.save(update_fields=["encashed_days", "updated_at"])
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("12"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError):
            enc.full_clean()

    def test_no_allocation_means_zero_available(self, tenant_a, employee_a, leave_type_a):
        """No LeaveAllocation row for this (employee, leave_type, year) -> 0 days available."""
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=2099, days=Decimal("1"), rate_per_day=Decimal("100"),
        )
        with pytest.raises(ValidationError):
            enc.full_clean()


# ============================================================
# LeaveEncashment model — ENC- numbering
# ============================================================
class TestLeaveEncashmentNumbering:
    def test_number_prefix(self, draft_encashment_a):
        assert draft_encashment_a.number.startswith("ENC-")

    def test_number_format(self, draft_encashment_a):
        assert draft_encashment_a.number == "ENC-00001"

    def test_sequential_within_tenant(self, tenant_a, employee_a, leave_type_a, leave_allocation_a, draft_encashment_a):
        from apps.hrm.models import LeaveEncashment
        enc2 = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("1"), rate_per_day=Decimal("50"),
        )
        assert enc2.number == "ENC-00002"

    def test_numbering_isolated_across_tenants(
            self, draft_encashment_a, tenant_b, employee_b, leave_type_b_encashable, leave_allocation_b):
        from apps.hrm.models import LeaveEncashment
        enc_b = LeaveEncashment.objects.create(
            tenant=tenant_b, employee=employee_b, leave_type=leave_type_b_encashable,
            year=leave_allocation_b.year, days=Decimal("1"), rate_per_day=Decimal("50"),
        )
        assert draft_encashment_a.number == "ENC-00001"
        assert enc_b.number == "ENC-00001"

    def test_unique_together_tenant_number(self, tenant_a, draft_encashment_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveEncashment
        with pytest.raises(IntegrityError):
            LeaveEncashment.objects.create(
                tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
                year=2026, number="ENC-00001", days=Decimal("1"), rate_per_day=Decimal("1"),
            )

    def test_str(self, draft_encashment_a):
        s = str(draft_encashment_a)
        assert draft_encashment_a.number in s


# ============================================================
# LeaveEncashment workflow — submit / approve / mark_paid / reject / cancel
# ============================================================
class TestLeaveEncashmentWorkflow:
    def test_submit_draft_to_pending(self, client_a, draft_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_submit", args=[draft_encashment_a.pk]))
        assert resp.status_code == 302
        draft_encashment_a.refresh_from_db()
        assert draft_encashment_a.status == "pending"

    def test_submit_noop_when_not_draft(self, client_a, pending_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_submit", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "pending"

    def test_approve_pending_to_approved(self, client_a, admin_user, pending_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "approved"
        assert pending_encashment_a.approver == admin_user
        assert pending_encashment_a.approved_at is not None

    def test_approve_increments_allocation_encashed_days(self, client_a, pending_encashment_a, leave_allocation_a):
        assert leave_allocation_a.encashed_days == Decimal("0")
        original_allocated = leave_allocation_a.allocated_days
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("5")
        assert leave_allocation_a.allocated_days == original_allocated  # UNCHANGED

    def test_approve_drops_balance(self, client_a, pending_encashment_a, leave_allocation_a):
        assert leave_allocation_a.balance == Decimal("21")
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.balance == Decimal("16")

    def test_mark_paid_approved_to_paid(self, client_a, pending_encashment_a):
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        pending_encashment_a.refresh_from_db()
        resp = client_a.post(
            reverse("hrm:leaveencashment_mark_paid", args=[pending_encashment_a.pk]),
            {"payment_reference": "TXN-001"})
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "paid"
        assert pending_encashment_a.paid_on == timezone.localdate()
        assert pending_encashment_a.payment_reference == "TXN-001"

    def test_mark_paid_noop_when_not_approved(self, client_a, pending_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_mark_paid", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "pending"
        assert pending_encashment_a.paid_on is None

    def test_reject_pending_to_rejected(self, client_a, pending_encashment_a):
        resp = client_a.post(
            reverse("hrm:leaveencashment_reject", args=[pending_encashment_a.pk]),
            {"decision_note": "Insufficient documentation"})
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "rejected"
        assert pending_encashment_a.decision_note == "Insufficient documentation"

    def test_reject_does_not_touch_allocation(self, client_a, pending_encashment_a, leave_allocation_a):
        client_a.post(reverse("hrm:leaveencashment_reject", args=[pending_encashment_a.pk]))
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("0")

    def test_cancel_draft(self, client_a, draft_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_cancel", args=[draft_encashment_a.pk]))
        assert resp.status_code == 302
        draft_encashment_a.refresh_from_db()
        assert draft_encashment_a.status == "cancelled"

    def test_cancel_pending(self, client_a, pending_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_cancel", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "cancelled"

    def test_cancel_noop_once_approved(self, client_a, pending_encashment_a, leave_allocation_a):
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "approved"
        resp = client_a.post(reverse("hrm:leaveencashment_cancel", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "approved"  # unchanged — no-op
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("5")  # not reverted


# ============================================================
# LeaveEncashment workflow — edit/delete guards on decided rows
# ============================================================
class TestLeaveEncashmentEditDeleteGuards:
    def test_edit_get_allowed_for_draft(self, client_a, draft_encashment_a):
        resp = client_a.get(reverse("hrm:leaveencashment_edit", args=[draft_encashment_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_allowed_for_pending(self, client_a, pending_encashment_a):
        resp = client_a.get(reverse("hrm:leaveencashment_edit", args=[pending_encashment_a.pk]))
        assert resp.status_code == 200

    def test_edit_redirects_when_approved(self, client_a, pending_encashment_a):
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        pending_encashment_a.refresh_from_db()
        resp = client_a.get(reverse("hrm:leaveencashment_edit", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:leaveencashment_detail", args=[pending_encashment_a.pk])

    def test_edit_post_does_not_mutate_when_approved(self, client_a, pending_encashment_a):
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        pending_encashment_a.refresh_from_db()
        original_days = pending_encashment_a.days
        client_a.post(reverse("hrm:leaveencashment_edit", args=[pending_encashment_a.pk]), {
            "employee": pending_encashment_a.employee_id,
            "leave_type": pending_encashment_a.leave_type_id,
            "year": pending_encashment_a.year,
            "days": "999",
            "rate_per_day": pending_encashment_a.rate_per_day,
        })
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.days == original_days  # unchanged — locked

    def test_delete_allowed_for_draft(self, client_a, draft_encashment_a):
        from apps.hrm.models import LeaveEncashment
        pk = draft_encashment_a.pk
        resp = client_a.post(reverse("hrm:leaveencashment_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LeaveEncashment.objects.filter(pk=pk).exists()

    def test_delete_allowed_for_pending(self, client_a, pending_encashment_a):
        from apps.hrm.models import LeaveEncashment
        pk = pending_encashment_a.pk
        resp = client_a.post(reverse("hrm:leaveencashment_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LeaveEncashment.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_approved(self, client_a, pending_encashment_a):
        from apps.hrm.models import LeaveEncashment
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        pk = pending_encashment_a.pk
        resp = client_a.post(reverse("hrm:leaveencashment_delete", args=[pk]))
        assert resp.status_code == 302
        assert LeaveEncashment.objects.filter(pk=pk).exists()  # not deleted

    def test_delete_blocked_when_rejected(self, client_a, pending_encashment_a):
        from apps.hrm.models import LeaveEncashment
        client_a.post(reverse("hrm:leaveencashment_reject", args=[pending_encashment_a.pk]))
        pk = pending_encashment_a.pk
        resp = client_a.post(reverse("hrm:leaveencashment_delete", args=[pk]))
        assert resp.status_code == 302
        assert LeaveEncashment.objects.filter(pk=pk).exists()  # not deleted

    def test_delete_requires_post(self, client_a, draft_encashment_a):
        from apps.hrm.models import LeaveEncashment
        resp = client_a.get(reverse("hrm:leaveencashment_delete", args=[draft_encashment_a.pk]))
        assert resp.status_code == 405
        assert LeaveEncashment.objects.filter(pk=draft_encashment_a.pk).exists()


# ============================================================
# LeaveEncashment workflow — approve balance re-check (double approval race)
# ============================================================
class TestLeaveEncashmentApproveBalanceGuard:
    def test_approve_refuses_when_days_exceed_balance_at_approval_time(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """Two pending encashments totalling more than the 21-day balance: approving the first
        (15 days) succeeds; approving the second (10 days) must then be refused because only
        6 days remain — and must not mutate anything."""
        from apps.hrm.models import LeaveEncashment
        enc1 = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("15"), rate_per_day=Decimal("100"),
            status="pending",
        )
        enc2 = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("10"), rate_per_day=Decimal("100"),
            status="pending",
        )
        resp1 = client_a.post(reverse("hrm:leaveencashment_approve", args=[enc1.pk]))
        assert resp1.status_code == 302
        enc1.refresh_from_db()
        assert enc1.status == "approved"

        resp2 = client_a.post(reverse("hrm:leaveencashment_approve", args=[enc2.pk]))
        assert resp2.status_code == 302
        enc2.refresh_from_db()
        assert enc2.status == "pending"  # blocked — still pending, not approved

        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("15")  # only enc1's days consumed
        assert leave_allocation_a.balance == Decimal("6")

    def test_second_approval_attempt_does_not_double_consume(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """Approving enc2 again after the block must still refuse (idempotent no-op)."""
        from apps.hrm.models import LeaveEncashment
        enc1 = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("20"), rate_per_day=Decimal("100"),
            status="pending",
        )
        enc2 = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("5"), rate_per_day=Decimal("100"),
            status="pending",
        )
        client_a.post(reverse("hrm:leaveencashment_approve", args=[enc1.pk]))
        client_a.post(reverse("hrm:leaveencashment_approve", args=[enc2.pk]))
        client_a.post(reverse("hrm:leaveencashment_approve", args=[enc2.pk]))  # retry
        enc2.refresh_from_db()
        assert enc2.status == "pending"
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("20")


# ============================================================
# LeaveEncashment workflow — authorization (@tenant_admin_required)
# ============================================================
class TestLeaveEncashmentWorkflowAuthorization:
    def test_nonadmin_approve_403(self, member_client, pending_encashment_a):
        resp = member_client.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        assert resp.status_code == 403
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "pending"

    def test_nonadmin_reject_403(self, member_client, pending_encashment_a):
        resp = member_client.post(reverse("hrm:leaveencashment_reject", args=[pending_encashment_a.pk]))
        assert resp.status_code == 403
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "pending"

    def test_nonadmin_mark_paid_403(self, member_client, pending_encashment_a, client_a):
        client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        pending_encashment_a.refresh_from_db()
        resp = member_client.post(reverse("hrm:leaveencashment_mark_paid", args=[pending_encashment_a.pk]))
        assert resp.status_code == 403
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "approved"  # unchanged, not "paid"

    def test_nonadmin_submit_allowed(self, member_client, draft_encashment_a):
        """submit is @login_required-only — a non-admin may submit their own request."""
        resp = member_client.post(reverse("hrm:leaveencashment_submit", args=[draft_encashment_a.pk]))
        assert resp.status_code == 302
        draft_encashment_a.refresh_from_db()
        assert draft_encashment_a.status == "pending"

    def test_nonadmin_cancel_allowed(self, member_client, draft_encashment_a):
        """cancel is @login_required-only."""
        resp = member_client.post(reverse("hrm:leaveencashment_cancel", args=[draft_encashment_a.pk]))
        assert resp.status_code == 302
        draft_encashment_a.refresh_from_db()
        assert draft_encashment_a.status == "cancelled"

    def test_admin_approve_succeeds(self, client_a, pending_encashment_a):
        resp = client_a.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        assert resp.status_code == 302
        pending_encashment_a.refresh_from_db()
        assert pending_encashment_a.status == "approved"

    def test_template_gate_is_not_the_only_guard(self, member_client, pending_encashment_a):
        """Even a crafted POST straight to the approve endpoint must be blocked server-side."""
        resp = member_client.post(
            reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]),
            {"decision_note": "forged"})
        assert resp.status_code == 403


# ============================================================
# LeaveEncashment list/detail views
# ============================================================
class TestLeaveEncashmentListDetailViews:
    def test_list_ok(self, client_a, pending_encashment_a):
        resp = client_a.get(reverse("hrm:leaveencashment_list"))
        assert resp.status_code == 200
        assert pending_encashment_a.number.encode() in resp.content

    def test_filter_by_status(self, client_a, draft_encashment_a):
        from apps.hrm.models import LeaveEncashment
        LeaveEncashment.objects.filter(pk=draft_encashment_a.pk).update(status="draft")
        resp = client_a.get(reverse("hrm:leaveencashment_list"), {"status": "draft"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_encashment_a.pk in pks

    def test_create_view_post(self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveEncashment
        resp = client_a.post(reverse("hrm:leaveencashment_create"), {
            "employee": employee_a.pk,
            "leave_type": leave_type_a.pk,
            "year": leave_allocation_a.year,
            "days": "3",
            "rate_per_day": "120",
        })
        assert resp.status_code == 302
        enc = LeaveEncashment.objects.get(tenant=tenant_a, employee=employee_a)
        assert enc.tenant_id == tenant_a.pk
        assert enc.status == "draft"
        assert enc.amount == Decimal("360.00")

    def test_detail_ok(self, client_a, pending_encashment_a):
        resp = client_a.get(reverse("hrm:leaveencashment_detail", args=[pending_encashment_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == pending_encashment_a.pk

    def test_detail_has_allocation_in_context(self, client_a, pending_encashment_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveencashment_detail", args=[pending_encashment_a.pk]))
        assert resp.context["allocation"].pk == leave_allocation_a.pk


# ============================================================
# LeaveEncashmentForm — excluded fields + narrowed leave_type dropdown
# ============================================================
class TestLeaveEncashmentForm:
    def test_excludes_workflow_and_derived_fields(self):
        from apps.hrm.forms import LeaveEncashmentForm
        excluded = {"amount", "status", "approver", "approved_at", "paid_on",
                    "payment_reference", "decision_note", "number", "tenant"}
        assert not (excluded & set(LeaveEncashmentForm.Meta.fields))

    def test_leave_type_queryset_narrowed_to_encashable(
            self, tenant_a, leave_type_a, non_encashable_type_a):
        from apps.hrm.forms import LeaveEncashmentForm
        form = LeaveEncashmentForm(tenant=tenant_a)
        qs = form.fields["leave_type"].queryset
        assert leave_type_a in qs
        assert non_encashable_type_a not in qs

    def test_required_fields_missing(self, tenant_a):
        from apps.hrm.forms import LeaveEncashmentForm
        form = LeaveEncashmentForm({}, tenant=tenant_a)
        assert not form.is_valid()
        for f in ("employee", "leave_type", "year", "days"):
            assert f in form.errors

    def test_valid_form_saves(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.forms import LeaveEncashmentForm
        form = LeaveEncashmentForm({
            "employee": employee_a.pk, "leave_type": leave_type_a.pk,
            "year": leave_allocation_a.year, "days": "4", "rate_per_day": "80",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        obj.save()
        assert obj.amount == Decimal("320.00")

    def test_invalid_when_days_exceed_balance(self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.forms import LeaveEncashmentForm
        form = LeaveEncashmentForm({
            "employee": employee_a.pk, "leave_type": leave_type_a.pk,
            "year": leave_allocation_a.year, "days": "999", "rate_per_day": "80",
        }, tenant=tenant_a)
        assert not form.is_valid()


# ============================================================
# LeaveAllocationForm — manual allocated_days edit resets carried_forward
# ============================================================
class TestLeaveAllocationFormCarryForwardReset:
    def test_manual_allocated_days_edit_resets_carried_forward(self, tenant_a, leave_allocation_a):
        from apps.hrm.forms import LeaveAllocationForm
        leave_allocation_a.carried_forward = Decimal("5")
        leave_allocation_a.save(update_fields=["carried_forward", "updated_at"])
        form = LeaveAllocationForm({
            "employee": leave_allocation_a.employee_id,
            "leave_type": leave_allocation_a.leave_type_id,
            "year": leave_allocation_a.year,
            "allocated_days": "30",
            "note": "",
            "status": "active",
        }, instance=leave_allocation_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.carried_forward == Decimal("0")
        assert obj.allocated_days == Decimal("30")

    def test_unrelated_field_edit_does_not_reset_carried_forward(self, tenant_a, leave_allocation_a):
        from apps.hrm.forms import LeaveAllocationForm
        leave_allocation_a.carried_forward = Decimal("5")
        leave_allocation_a.save(update_fields=["carried_forward", "updated_at"])
        form = LeaveAllocationForm({
            "employee": leave_allocation_a.employee_id,
            "leave_type": leave_allocation_a.leave_type_id,
            "year": leave_allocation_a.year,
            "allocated_days": str(leave_allocation_a.allocated_days),
            "note": "Updated note only",
            "status": "active",
        }, instance=leave_allocation_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.carried_forward == Decimal("5")  # unchanged


# ============================================================
# Leave Policy engine — leave_accrual_run
# ============================================================
class TestLeaveAccrualRun:
    def test_annual_type_sets_allocated_to_grant(self, client_a, tenant_a, employee_a, leave_type_a):
        """leave_type_a: annual, accrual_days=21, max_balance=30."""
        from apps.hrm.models import LeaveAllocation
        resp = client_a.post(reverse("hrm:leave_accrual_run"), {"year": "2026"})
        assert resp.status_code == 302
        alloc = LeaveAllocation.objects.get(tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2026)
        assert alloc.allocated_days == Decimal("21")
        assert alloc.status == "active"

    def test_monthly_type_past_year_fully_accrues_12_months(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import LeaveType, LeaveAllocation
        monthly = LeaveType.objects.create(
            tenant=tenant_a, name="Casual Leave", code="CL", accrual_rule="monthly",
            accrual_days=Decimal("1"),
        )
        resp = client_a.post(reverse("hrm:leave_accrual_run"), {"year": "2020"})  # a past year
        assert resp.status_code == 302
        alloc = LeaveAllocation.objects.get(tenant=tenant_a, employee=employee_a, leave_type=monthly, year=2020)
        assert alloc.allocated_days == Decimal("12")

    def test_monthly_type_current_year_accrues_to_current_month(
            self, client_a, tenant_a, employee_a):
        from apps.hrm.models import LeaveType, LeaveAllocation
        monthly = LeaveType.objects.create(
            tenant=tenant_a, name="Casual Leave", code="CL", accrual_rule="monthly",
            accrual_days=Decimal("1"),
        )
        today = timezone.localdate()
        resp = client_a.post(reverse("hrm:leave_accrual_run"), {"year": str(today.year)})
        assert resp.status_code == 302
        alloc = LeaveAllocation.objects.get(
            tenant=tenant_a, employee=employee_a, leave_type=monthly, year=today.year)
        assert alloc.allocated_days == Decimal(str(today.month))

    def test_monthly_type_future_year_accrues_zero(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import LeaveType, LeaveAllocation
        monthly = LeaveType.objects.create(
            tenant=tenant_a, name="Casual Leave", code="CL", accrual_rule="monthly",
            accrual_days=Decimal("2"),
        )
        future_year = timezone.localdate().year + 5
        resp = client_a.post(reverse("hrm:leave_accrual_run"), {"year": str(future_year)})
        assert resp.status_code == 302
        alloc = LeaveAllocation.objects.get(
            tenant=tenant_a, employee=employee_a, leave_type=monthly, year=future_year)
        assert alloc.allocated_days == Decimal("0")

    def test_capped_at_max_balance(self, client_a, tenant_a, employee_a, leave_type_a):
        """leave_type_a: accrual_days=21, max_balance=30 -> no cap hit here; use a tighter cap type."""
        from apps.hrm.models import LeaveType, LeaveAllocation
        capped = LeaveType.objects.create(
            tenant=tenant_a, name="Capped Leave", code="CAP", accrual_rule="annual",
            accrual_days=Decimal("25"), max_balance=Decimal("10"),
        )
        resp = client_a.post(reverse("hrm:leave_accrual_run"), {"year": "2026"})
        assert resp.status_code == 302
        alloc = LeaveAllocation.objects.get(tenant=tenant_a, employee=employee_a, leave_type=capped, year=2026)
        assert alloc.allocated_days == Decimal("10")  # capped, not 25

    def test_idempotent_rerun_gives_identical_allocated_days(self, client_a, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveAllocation
        client_a.post(reverse("hrm:leave_accrual_run"), {"year": "2026"})
        alloc = LeaveAllocation.objects.get(tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2026)
        first_days = alloc.allocated_days
        client_a.post(reverse("hrm:leave_accrual_run"), {"year": "2026"})
        alloc.refresh_from_db()
        assert alloc.allocated_days == first_days

    def test_only_touches_acting_tenant(
            self, client_a, tenant_a, tenant_b, employee_a, employee_b, leave_type_a, leave_type_b):
        from apps.hrm.models import LeaveAllocation
        client_a.post(reverse("hrm:leave_accrual_run"), {"year": "2026"})
        assert not LeaveAllocation.objects.filter(tenant=tenant_b).exists()

    def test_regression_encashed_days_not_restored_by_accrual_rerun(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """Critical double-spend regression: after approving an encashment that consumes 5 days,
        re-running leave_accrual_run for that year must NOT restore allocated_days in a way that
        undoes the encashment — encashed_days stays and balance stays reduced."""
        from apps.hrm.models import LeaveEncashment
        enc = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("5"), rate_per_day=Decimal("100"),
            status="pending",
        )
        client_a.post(reverse("hrm:leaveencashment_approve", args=[enc.pk]))
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("5")
        assert leave_allocation_a.balance == Decimal("16")

        # Re-run accrual for the same year.
        client_a.post(reverse("hrm:leave_accrual_run"), {"year": str(leave_allocation_a.year)})
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.encashed_days == Decimal("5")  # untouched
        assert leave_allocation_a.allocated_days == Decimal("21")  # accrual target unchanged
        assert leave_allocation_a.balance == Decimal("16")  # still reduced, not restored to 21


# ============================================================
# Leave Policy engine — leave_carryforward_run
# ============================================================
class TestLeaveCarryforwardRun:
    def test_dest_year_carried_forward_is_min_balance_and_cap(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """leave_type_a: max_carry_forward=5. balance=21 (allocated 21, 0 used/encashed) ->
        carry = min(21, 5) = 5."""
        from apps.hrm.models import LeaveAllocation
        resp = client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        assert resp.status_code == 302
        dst = LeaveAllocation.objects.get(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2027)
        assert dst.carried_forward == Decimal("5")

    def test_dest_allocated_days_never_exceeds_max_balance(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveAllocation
        # Pre-seed the dest year with an allocation already near the cap (30).
        LeaveAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2027,
            allocated_days=Decimal("28"), status="active",
        )
        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        dst = LeaveAllocation.objects.get(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2027)
        assert dst.allocated_days <= Decimal("30")

    def test_idempotent_rerun_does_not_double_add(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.models import LeaveAllocation
        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        dst = LeaveAllocation.objects.get(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2027)
        first_carried = dst.carried_forward
        first_allocated = dst.allocated_days
        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        dst.refresh_from_db()
        assert dst.carried_forward == first_carried
        assert dst.allocated_days == first_allocated

    def test_rerun_replaces_own_prior_contribution_not_doubles(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """Change the source balance between runs — the second run should REPLACE the first
        run's carried_forward contribution, not add to it."""
        from apps.hrm.models import LeaveAllocation, LeaveRequest
        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        dst = LeaveAllocation.objects.get(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2027)
        assert dst.carried_forward == Decimal("5")  # capped at max_carry_forward

        # Reduce the source-year balance (approve a leave request that eats into it).
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2026, 4, 5),
            status="approved",
        )
        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        dst.refresh_from_db()
        # Balance is still >= 5 (21 - 5 used = 16), so carry is still capped at 5 — but the
        # allocated_days must reflect a REPLACEMENT, not dst.allocated_days growing every re-run.
        assert dst.carried_forward == Decimal("5")

    def test_carryforward_nets_encashed_days(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """leave_type_a is both encashable (fixture) and carriable (max_carry_forward=5). Days
        already encashed must not also be carried forward."""
        from apps.hrm.models import LeaveEncashment, LeaveAllocation
        enc = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("21"), rate_per_day=Decimal("10"),
            status="pending",
        )
        client_a.post(reverse("hrm:leaveencashment_approve", args=[enc.pk]))
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.balance == Decimal("0")  # fully encashed

        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        dst = LeaveAllocation.objects.filter(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a, year=2027).first()
        # Either no dest row was created (touched=0, balance was 0) or carried_forward is 0.
        if dst is not None:
            assert dst.carried_forward == Decimal("0")

    def test_only_touches_acting_tenant(
            self, client_a, tenant_a, tenant_b, employee_a, employee_b, leave_type_a, leave_type_b,
            leave_allocation_a):
        from apps.hrm.models import LeaveAllocation
        client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "2026"})
        assert not LeaveAllocation.objects.filter(tenant=tenant_b, year=2027).exists()


# ============================================================
# _policy_year bounds
# ============================================================
class TestPolicyYearBounds:
    def test_oversized_year_falls_back_to_current_year(self, client_a):
        resp = client_a.get(reverse("hrm:leave_policy"), {"year": "999999999999"})
        assert resp.status_code == 200
        assert resp.context["year"] == timezone.localdate().year

    def test_below_2000_falls_back_to_current_year(self, client_a):
        resp = client_a.get(reverse("hrm:leave_policy"), {"year": "1999"})
        assert resp.status_code == 200
        assert resp.context["year"] == timezone.localdate().year

    def test_non_digit_falls_back_to_current_year(self, client_a):
        resp = client_a.get(reverse("hrm:leave_policy"), {"year": "abc"})
        assert resp.status_code == 200
        assert resp.context["year"] == timezone.localdate().year

    def test_valid_year_in_window_is_honored(self, client_a):
        resp = client_a.get(reverse("hrm:leave_policy"), {"year": "2030"})
        assert resp.status_code == 200
        assert resp.context["year"] == 2030

    def test_accrual_run_with_oversized_year_does_not_500(self, client_a):
        resp = client_a.post(reverse("hrm:leave_accrual_run"), {"year": "999999999999"})
        assert resp.status_code == 302  # redirect, not a 500/DataError

    def test_carryforward_run_with_non_digit_year_does_not_500(self, client_a):
        resp = client_a.post(reverse("hrm:leave_carryforward_run"), {"year": "not-a-year"})
        assert resp.status_code == 302


# ============================================================
# Offboarding integration — compute_leave_encashment nets out encashed days
# ============================================================
class TestComputeLeaveEncashmentNetsEncashedDays:
    def test_encashed_days_reduce_computed_balance(
            self, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        from apps.hrm.services import compute_leave_encashment
        days_before, _ = compute_leave_encashment(employee_a)
        assert days_before == Decimal("21")

        leave_allocation_a.encashed_days = Decimal("8")
        leave_allocation_a.save(update_fields=["encashed_days", "updated_at"])

        days_after, _ = compute_leave_encashment(employee_a)
        assert days_after == Decimal("13")  # 21 - 8

    def test_approved_encashment_via_view_reduces_final_settlement_computation(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a):
        """An approved LeaveEncashment (via the real workflow) must reduce what
        compute_leave_encashment pays out at offboarding — no double payment."""
        from apps.hrm.models import LeaveEncashment
        from apps.hrm.services import compute_leave_encashment
        enc = LeaveEncashment.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            year=leave_allocation_a.year, days=Decimal("6"), rate_per_day=Decimal("100"),
            status="pending",
        )
        client_a.post(reverse("hrm:leaveencashment_approve", args=[enc.pk]))
        days, _ = compute_leave_encashment(employee_a)
        assert days == Decimal("15")  # 21 - 6


# ============================================================
# Multi-tenant IDOR sweep — LeaveEncashment
# ============================================================
class TestLeaveEncashmentIDOR:
    def test_detail_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.get(reverse("hrm:leaveencashment_detail", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.get(reverse("hrm:leaveencashment_edit", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_edit", args=[encashment_b.pk]), {
            "employee": encashment_b.employee_id, "leave_type": encashment_b.leave_type_id,
            "year": encashment_b.year, "days": "999", "rate_per_day": "1",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, encashment_b):
        from apps.hrm.models import LeaveEncashment
        resp = client_a.post(reverse("hrm:leaveencashment_delete", args=[encashment_b.pk]))
        assert resp.status_code == 404
        assert LeaveEncashment.objects.filter(pk=encashment_b.pk).exists()

    def test_submit_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_submit", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_approve", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_reject_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_reject", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_mark_paid_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_mark_paid", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_cancel", args=[encashment_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_tenant_b(self, client_a, pending_encashment_a, encashment_b):
        resp = client_a.get(reverse("hrm:leaveencashment_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_encashment_a.pk in pks
        assert encashment_b.pk not in pks

    def test_encashment_b_status_unchanged_after_idor_approve_attempt(self, client_a, encashment_b):
        resp = client_a.post(reverse("hrm:leaveencashment_approve", args=[encashment_b.pk]))
        assert resp.status_code == 404
        encashment_b.refresh_from_db()
        assert encashment_b.status == "pending"

    def test_encashment_b_allocation_unchanged_after_idor_approve_attempt(
            self, client_a, encashment_b, leave_allocation_b):
        original_encashed = leave_allocation_b.encashed_days
        client_a.post(reverse("hrm:leaveencashment_approve", args=[encashment_b.pk]))
        leave_allocation_b.refresh_from_db()
        assert leave_allocation_b.encashed_days == original_encashed


# ============================================================
# Anonymous access
# ============================================================
class TestAnonymousBlockedLeaveEncashmentEndpoints:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:leaveencashment_list", []),
        ("hrm:leaveencashment_create", []),
        ("hrm:leave_policy", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# CSRF enforcement on POST-only endpoints
# ============================================================
class TestCSRFEnforcementLeaveEncashmentEndpoints:
    def test_delete_enforces_csrf(self, admin_user, draft_encashment_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:leaveencashment_delete", args=[draft_encashment_a.pk]))
        assert resp.status_code == 403

    def test_approve_enforces_csrf(self, admin_user, pending_encashment_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:leaveencashment_approve", args=[pending_encashment_a.pk]))
        assert resp.status_code == 403

    def test_accrual_run_enforces_csrf(self, admin_user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:leave_accrual_run"), {"year": "2026"})
        assert resp.status_code == 403


# ============================================================
# Performance — leaveencashment_list and leaveallocation_detail query counts
# ============================================================
class TestLeaveEncashmentPerformance:
    def test_list_query_count_bounded_with_many_rows(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a,
            django_assert_max_num_queries):
        from apps.hrm.models import LeaveEncashment
        for i in range(15):
            LeaveEncashment.objects.create(
                tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
                year=leave_allocation_a.year, days=Decimal("1"), rate_per_day=Decimal("10"),
            )
        with django_assert_max_num_queries(12):
            resp = client_a.get(reverse("hrm:leaveencashment_list"))
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) >= 10


class TestLeaveAllocationDetailPerformance:
    def test_detail_query_count_bounded_with_many_requests_and_encashments(
            self, client_a, tenant_a, employee_a, leave_type_a, leave_allocation_a,
            django_assert_max_num_queries):
        from apps.hrm.models import LeaveRequest, LeaveEncashment
        for i in range(10):
            LeaveRequest.objects.create(
                tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
                start_date=datetime.date(2026, 1, 1) + datetime.timedelta(days=i * 3),
                end_date=datetime.date(2026, 1, 2) + datetime.timedelta(days=i * 3),
            )
            LeaveEncashment.objects.create(
                tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
                year=leave_allocation_a.year, days=Decimal("1"), rate_per_day=Decimal("10"),
            )
        with django_assert_max_num_queries(12):
            resp = client_a.get(reverse("hrm:leaveallocation_detail", args=[leave_allocation_a.pk]))
        assert resp.status_code == 200
        assert len(resp.context["requests"]) >= 10
        assert len(resp.context["encashments"]) >= 10
