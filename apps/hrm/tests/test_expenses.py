"""Tests for HRM 3.34 Expense Management sub-module: ``ExpenseCategory`` (admin-config CRUD) +
``ExpenseClaim`` (own-or-admin CRUD, ``ECL-#####``) + inline ``ExpenseClaimLine`` (draft-only,
receipt uploads) + the lean 2-stage manager -> finance approval workflow (submit / manager_approve /
approve / reject / cancel / reimburse).

Mirrors ``test_assets.py`` / ``test_analytics_dashboard.py`` — same fixture style (local
``pytest.fixture``s in this module reusing the shared root/HRM conftest), hand-verified computed
properties, IDOR, access-control, own-vs-admin self-service scoping (``_ss_scope`` /
``_can_manage_own_child`` — the same 3.25/3.26 helpers), self-approval blocks (``_is_own_hr_request``),
and a query-count-ceiling regression guard for the ``total_amount`` prefetch-cache-aware N+1 fix.

Covers:
  - ``ExpenseClaimLine.policy_violation``/``violation_reason`` (per-claim-limit + receipt-required-
    above, both None-guarded) and ``ExpenseClaim.has_violations``/``total_amount`` (prefetch-cache-
    aware vs standalone-aggregate, empty claim -> ``Decimal("0")``).
  - Model basics (``__str__``, defaults, ``unique_together``).
  - Full CRUD + the 2-stage workflow (submit/manager_approve/approve/reject/cancel/reimburse), every
    stage-skip guard, the reject stage-appropriate approver-pair stamp, and the self-approval block on
    all four admin actions (including the just-added reimburse guard).
  - Draft-only editing (claim + inline lines) once a claim leaves draft.
  - ``ExpenseCategoryForm``/``ExpenseClaimForm``/``ExpenseClaimLineForm`` validation (incl. the shared
    receipt upload extension guard).
  - Category delete guard (blocked while referenced by a line).
  - Access control (anonymous redirect, non-admin 200 on lists / 403 on admin-only category writes),
    own-vs-admin self-service scoping + cross-employee IDOR, multi-tenant IDOR (404 + list isolation),
    CSRF enforcement, and an N+1 query-count-ceiling regression guard on ``expenseclaim_list``.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ============================================================
# Shared fixtures
# ============================================================

def _client_for(party, tenant, *, email, username, is_admin=False):
    """A fresh logged-in Client for a NEW user linked (via ``party``) to an EmployeeProfile —
    mirrors ``test_selfservice_security.py``'s helper for own-vs-admin / self-approval fixtures."""
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
    scoping tests (sees/manages only employee_a's claims)."""
    return _client_for(employee_a.party, tenant_a, email="owner@acme.com", username="owner_acme")


@pytest.fixture
def other_employee_client(tenant_a, employee_a2):
    """A NON-ADMIN user whose linked EmployeeProfile IS employee_a2 — a DIFFERENT employee from
    employee_a, same tenant (cross-employee IDOR probes)."""
    return _client_for(employee_a2.party, tenant_a, email="other@acme.com", username="other_acme")


@pytest.fixture
def self_admin_client(tenant_a, employee_a):
    """A TENANT ADMIN whose linked EmployeeProfile IS employee_a — the self-approval-block subject
    (an admin who is ALSO the claim's employee)."""
    return _client_for(employee_a.party, tenant_a, email="selfadmin@acme.com",
                        username="selfadmin_acme", is_admin=True)


@pytest.fixture
def category_a(db, tenant_a):
    """An ExpenseCategory for tenant_a with BOTH policy limits set: per_claim_limit=500,
    requires_receipt_above=100."""
    from apps.hrm.models import ExpenseCategory
    return ExpenseCategory.objects.create(
        tenant=tenant_a, name="Travel", code="TRAVEL",
        per_claim_limit=Decimal("500.00"), requires_receipt_above=Decimal("100.00"),
    )


@pytest.fixture
def category_no_limits_a(db, tenant_a):
    """An ExpenseCategory for tenant_a with NO policy limits (the None-guard cases)."""
    from apps.hrm.models import ExpenseCategory
    return ExpenseCategory.objects.create(tenant=tenant_a, name="Miscellaneous", code="MISC")


@pytest.fixture
def category_b(db, tenant_b):
    """An ExpenseCategory belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ExpenseCategory
    return ExpenseCategory.objects.create(
        tenant=tenant_b, name="Travel B", code="TRAVELB",
        per_claim_limit=Decimal("500.00"), requires_receipt_above=Decimal("100.00"),
    )


@pytest.fixture
def draft_claim_a(db, tenant_a, employee_a):
    """A draft ExpenseClaim for employee_a/tenant_a — no lines yet."""
    from apps.hrm.models import ExpenseClaim
    return ExpenseClaim.objects.create(
        tenant=tenant_a, employee=employee_a, title="Client Site Visit",
        purpose="Quarterly review with client",
        period_start=datetime.date(2026, 7, 1), period_end=datetime.date(2026, 7, 5),
    )


@pytest.fixture
def line_a(db, tenant_a, draft_claim_a, category_a):
    """A clean (non-violating) ExpenseClaimLine on draft_claim_a — amount 80.00, under both the 500
    per-claim limit and the 100 receipt threshold, no receipt attached."""
    from apps.hrm.models import ExpenseClaimLine
    return ExpenseClaimLine.objects.create(
        tenant=tenant_a, claim=draft_claim_a, category=category_a,
        expense_date=datetime.date(2026, 7, 2), merchant="Uber", amount=Decimal("80.00"),
    )


@pytest.fixture
def submitted_claim_a(db, tenant_a, employee_a, category_a):
    """An INDEPENDENT ExpenseClaim (own row, not draft_claim_a) already 'submitted' with one clean
    line — the manager-approve / reject-stage-1 pre-req."""
    from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
    claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a, title="Conference Trip")
    ExpenseClaimLine.objects.create(
        tenant=tenant_a, claim=claim, category=category_a,
        expense_date=datetime.date(2026, 7, 2), amount=Decimal("80.00"))
    claim.status = "submitted"
    claim.save(update_fields=["status", "updated_at"])
    return claim


@pytest.fixture
def manager_approved_claim_a(db, tenant_a, employee_a, category_a, admin_user):
    """An INDEPENDENT ExpenseClaim already 'manager_approved' (manager fields stamped by admin_user,
    a DIFFERENT admin from the claim's employee_a) — the finance-approve / reject-stage-2 / reimburse
    pre-req."""
    from django.utils import timezone
    from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
    claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a, title="Manager Approved Trip")
    ExpenseClaimLine.objects.create(
        tenant=tenant_a, claim=claim, category=category_a,
        expense_date=datetime.date(2026, 7, 2), amount=Decimal("80.00"))
    claim.status = "manager_approved"
    claim.manager_approver = admin_user
    claim.manager_approved_at = timezone.now()
    claim.save(update_fields=["status", "manager_approver", "manager_approved_at", "updated_at"])
    return claim


@pytest.fixture
def approved_claim_a(db, tenant_a, employee_a, category_a, admin_user):
    """An INDEPENDENT ExpenseClaim already 'approved' (both approver pairs stamped by admin_user) —
    the reimburse pre-req."""
    from django.utils import timezone
    from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
    claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a, title="Approved Trip")
    ExpenseClaimLine.objects.create(
        tenant=tenant_a, claim=claim, category=category_a,
        expense_date=datetime.date(2026, 7, 2), amount=Decimal("80.00"))
    claim.status = "approved"
    claim.manager_approver = admin_user
    claim.manager_approved_at = timezone.now()
    claim.finance_approver = admin_user
    claim.approved_at = timezone.now()
    claim.save(update_fields=["status", "manager_approver", "manager_approved_at",
                               "finance_approver", "approved_at", "updated_at"])
    return claim


@pytest.fixture
def claim_b(db, tenant_b, employee_b):
    """A draft ExpenseClaim belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ExpenseClaim
    return ExpenseClaim.objects.create(tenant=tenant_b, employee=employee_b, title="Globex Trip")


@pytest.fixture
def line_b(db, tenant_b, claim_b, category_b):
    """An ExpenseClaimLine belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ExpenseClaimLine
    return ExpenseClaimLine.objects.create(
        tenant=tenant_b, claim=claim_b, category=category_b,
        expense_date=datetime.date(2026, 7, 2), amount=Decimal("50.00"),
    )


@pytest.fixture
def many_claims_a(db, tenant_a, employee_a, employee_a2, category_a):
    """12 ExpenseClaims for tenant_a (split across employee_a/employee_a2), each with 2 lines — the
    N+1 query-count fixture for expenseclaim_list (proves total_amount/has_violations stay
    prefetch-cache-aware regardless of row count)."""
    from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
    claims = []
    for i in range(12):
        emp = employee_a if i % 2 == 0 else employee_a2
        claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=emp, title=f"Bulk Claim {i}")
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=claim, category=category_a,
            expense_date=datetime.date(2026, 7, 1), amount=Decimal("40.00"))
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=claim, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("60.00"))
        claims.append(claim)
    return claims


def _category_payload(**overrides):
    """A minimal-but-complete valid ExpenseCategoryForm POST payload."""
    data = {
        "name": "Meals", "code": "MEALS", "description": "",
        "per_claim_limit": "", "monthly_limit": "", "requires_receipt_above": "",
        "gl_account_hint": "", "is_active": "on",
    }
    data.update(overrides)
    return data


def _claim_payload(**overrides):
    """A minimal-but-complete valid ExpenseClaimForm POST payload."""
    data = {
        "title": "New Claim", "purpose": "", "period_start": "", "period_end": "", "currency": "",
    }
    data.update(overrides)
    return data


def _line_payload(category_pk, **overrides):
    """A minimal-but-complete valid ExpenseClaimLineForm POST payload (no receipt by default)."""
    data = {
        "category": category_pk, "expense_date": "2026-07-02", "merchant": "Uber",
        "description": "", "amount": "80.00",
    }
    data.update(overrides)
    return data


# ============================================================
# 1. Policy compliance (hand-verified)
# ============================================================

class TestExpenseClaimLinePolicyViolation:
    def test_under_both_limits_is_clean(self, tenant_a, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        line = ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("50.00"))
        assert line.policy_violation is False
        assert line.violation_reason == ""

    def test_over_per_claim_limit_flags(self, tenant_a, draft_claim_a, category_a):
        """amount=600 > per_claim_limit=500, WITH a receipt (isolates only the limit check)."""
        from apps.hrm.models import ExpenseClaimLine
        receipt = SimpleUploadedFile("receipt.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        line = ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("600.00"), receipt=receipt)
        assert line.policy_violation is True
        assert "Exceeds per-claim limit of 500.00" in line.violation_reason

    def test_over_receipt_threshold_without_receipt_flags(self, tenant_a, draft_claim_a, category_a):
        """amount=150 > requires_receipt_above=100, under per_claim_limit=500, no receipt."""
        from apps.hrm.models import ExpenseClaimLine
        line = ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("150.00"))
        assert line.policy_violation is True
        assert "Receipt required above 100.00" in line.violation_reason

    def test_over_receipt_threshold_with_receipt_is_clean(self, tenant_a, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        receipt = SimpleUploadedFile("receipt.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        line = ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("150.00"), receipt=receipt)
        assert line.policy_violation is False

    def test_over_both_limits_joins_both_reasons(self, tenant_a, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        line = ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("600.00"))
        assert line.policy_violation is True
        assert "Exceeds per-claim limit of 500.00" in line.violation_reason
        assert "Receipt required above 100.00" in line.violation_reason
        assert "; " in line.violation_reason

    def test_category_with_no_limits_never_flags(self, tenant_a, draft_claim_a, category_no_limits_a):
        from apps.hrm.models import ExpenseClaimLine
        line = ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_no_limits_a,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("999999.00"))
        assert line.policy_violation is False
        assert line.violation_reason == ""

    def test_no_category_guard_never_flags(self, tenant_a, draft_claim_a):
        """An in-memory line with category=None (never persistable — FK is required) never flags."""
        from apps.hrm.models import ExpenseClaimLine
        line = ExpenseClaimLine(
            tenant=tenant_a, claim=draft_claim_a, category=None,
            expense_date=datetime.date(2026, 7, 2), amount=Decimal("999999.00"))
        assert line.policy_violation is False
        assert line.violation_reason == ""

    def test_no_amount_guard_never_flags(self, tenant_a, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        line = ExpenseClaimLine(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 2), amount=None)
        assert line.policy_violation is False


class TestExpenseClaimHasViolations:
    def test_no_lines_is_false(self, draft_claim_a):
        assert draft_claim_a.has_violations is False

    def test_all_clean_lines_is_false(self, tenant_a, draft_claim_a, category_a, line_a):
        assert draft_claim_a.has_violations is False

    def test_one_violating_line_is_true(self, tenant_a, draft_claim_a, category_a, line_a):
        from apps.hrm.models import ExpenseClaimLine
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 3), amount=Decimal("600.00"))
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.has_violations is True


class TestExpenseClaimTotalAmount:
    def test_empty_claim_is_decimal_zero(self, draft_claim_a):
        assert draft_claim_a.total_amount == Decimal("0")

    def test_standalone_aggregate(self, tenant_a, draft_claim_a, category_a, line_a):
        from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 3), amount=Decimal("20.00"))
        claim = ExpenseClaim.objects.get(pk=draft_claim_a.pk)  # NOT prefetched
        assert claim.total_amount == Decimal("100.00")

    def test_prefetched_cache_aware_zero_extra_queries(
            self, django_assert_max_num_queries, tenant_a, draft_claim_a, category_a, line_a):
        from apps.hrm.models import ExpenseClaim, ExpenseClaimLine
        ExpenseClaimLine.objects.create(
            tenant=tenant_a, claim=draft_claim_a, category=category_a,
            expense_date=datetime.date(2026, 7, 3), amount=Decimal("20.00"))
        claim = ExpenseClaim.objects.prefetch_related("lines__category").get(pk=draft_claim_a.pk)
        with django_assert_max_num_queries(0):
            assert claim.total_amount == Decimal("100.00")


# ============================================================
# 2. Model basics
# ============================================================

class TestExpenseCategoryModelBasics:
    def test_str_with_code(self, category_a):
        assert str(category_a) == f"{category_a.name} ({category_a.code})"

    def test_str_without_code(self, tenant_a):
        from apps.hrm.models import ExpenseCategory
        obj = ExpenseCategory.objects.create(tenant=tenant_a, name="No Code Cat")
        assert str(obj) == "No Code Cat"

    def test_default_is_active_true(self, tenant_a):
        from apps.hrm.models import ExpenseCategory
        obj = ExpenseCategory.objects.create(tenant=tenant_a, name="Defaults")
        assert obj.is_active is True

    def test_unique_together_tenant_name(self, tenant_a, category_a):
        from django.db import IntegrityError, transaction
        from apps.hrm.models import ExpenseCategory
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ExpenseCategory.objects.create(tenant=tenant_a, name=category_a.name)


class TestExpenseClaimModelBasics:
    def test_str_includes_number_and_title(self, draft_claim_a):
        assert draft_claim_a.number in str(draft_claim_a)
        assert draft_claim_a.title in str(draft_claim_a)

    def test_number_prefix(self, draft_claim_a):
        assert draft_claim_a.number.startswith("ECL-")

    def test_default_status_draft(self, draft_claim_a):
        assert draft_claim_a.status == "draft"

    def test_unique_together_tenant_number(self, tenant_a, draft_claim_a, employee_a):
        from django.db import IntegrityError, transaction
        from apps.hrm.models import ExpenseClaim
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ExpenseClaim.objects.create(
                    tenant=tenant_a, employee=employee_a, title="Dup", number=draft_claim_a.number)


# ============================================================
# 3. Forms
# ============================================================

class TestExpenseCategoryForm:
    def test_valid_payload_passes(self, tenant_a):
        from apps.hrm.forms import ExpenseCategoryForm
        form = ExpenseCategoryForm(data=_category_payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_negative_per_claim_limit_rejected(self, tenant_a):
        from apps.hrm.forms import ExpenseCategoryForm
        form = ExpenseCategoryForm(data=_category_payload(per_claim_limit="-10"), tenant=tenant_a)
        assert not form.is_valid()
        assert "per_claim_limit" in form.errors

    def test_negative_requires_receipt_above_rejected(self, tenant_a):
        from apps.hrm.forms import ExpenseCategoryForm
        form = ExpenseCategoryForm(data=_category_payload(requires_receipt_above="-5"), tenant=tenant_a)
        assert not form.is_valid()
        assert "requires_receipt_above" in form.errors

    def test_negative_monthly_limit_rejected(self, tenant_a):
        from apps.hrm.forms import ExpenseCategoryForm
        form = ExpenseCategoryForm(data=_category_payload(monthly_limit="-1"), tenant=tenant_a)
        assert not form.is_valid()
        assert "monthly_limit" in form.errors

    def test_tenant_not_a_field(self):
        from apps.hrm.forms import ExpenseCategoryForm
        assert "tenant" not in ExpenseCategoryForm.Meta.fields


class TestExpenseClaimForm:
    def test_valid_payload_passes(self, tenant_a):
        from apps.hrm.forms import ExpenseClaimForm
        form = ExpenseClaimForm(data=_claim_payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_period_end_before_start_rejected(self, tenant_a):
        from apps.hrm.forms import ExpenseClaimForm
        form = ExpenseClaimForm(
            data=_claim_payload(period_start="2026-07-10", period_end="2026-07-01"), tenant=tenant_a)
        assert not form.is_valid()
        assert "period_end" in form.errors

    def test_period_end_equal_start_passes(self, tenant_a):
        from apps.hrm.forms import ExpenseClaimForm
        form = ExpenseClaimForm(
            data=_claim_payload(period_start="2026-07-10", period_end="2026-07-10"), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_workflow_owned_fields_not_form_fields(self):
        from apps.hrm.forms import ExpenseClaimForm
        for field in ("status", "employee", "tenant", "number", "manager_approver",
                      "manager_approved_at", "finance_approver", "approved_at", "payment_method"):
            assert field not in ExpenseClaimForm.Meta.fields


class TestExpenseClaimLineForm:
    def test_valid_payload_passes(self, tenant_a, category_a):
        from apps.hrm.forms import ExpenseClaimLineForm
        form = ExpenseClaimLineForm(data=_line_payload(category_a.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_zero_amount_rejected(self, tenant_a, category_a):
        from apps.hrm.forms import ExpenseClaimLineForm
        form = ExpenseClaimLineForm(data=_line_payload(category_a.pk, amount="0"), tenant=tenant_a)
        assert not form.is_valid()
        assert "amount" in form.errors

    def test_negative_amount_rejected(self, tenant_a, category_a):
        from apps.hrm.forms import ExpenseClaimLineForm
        form = ExpenseClaimLineForm(data=_line_payload(category_a.pk, amount="-5"), tenant=tenant_a)
        assert not form.is_valid()
        assert "amount" in form.errors

    def test_exe_receipt_rejected(self, tenant_a, category_a):
        from apps.hrm.forms import ExpenseClaimLineForm
        exe_file = SimpleUploadedFile("malware.exe", b"MZ\x90\x00", content_type="application/octet-stream")
        form = ExpenseClaimLineForm(_line_payload(category_a.pk), {"receipt": exe_file}, tenant=tenant_a)
        assert not form.is_valid()
        assert "receipt" in form.errors

    def test_png_receipt_accepted(self, tenant_a, category_a):
        from apps.hrm.forms import ExpenseClaimLineForm
        png_file = SimpleUploadedFile("receipt.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        form = ExpenseClaimLineForm(_line_payload(category_a.pk), {"receipt": png_file}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_tenant_and_claim_not_fields(self):
        from apps.hrm.forms import ExpenseClaimLineForm
        assert "tenant" not in ExpenseClaimLineForm.Meta.fields
        assert "claim" not in ExpenseClaimLineForm.Meta.fields


# ============================================================
# 4. ExpenseCategory CRUD + access control
# ============================================================

class TestExpenseCategoryListView:
    def test_200(self, client_a, category_a):
        resp = client_a.get(reverse("hrm:expensecategory_list"))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/expenses/expensecategory/list.html"

    def test_search_by_name(self, client_a, category_a):
        resp = client_a.get(reverse("hrm:expensecategory_list"), {"q": "Travel"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert category_a.pk in pks

    def test_search_no_match(self, client_a, category_a):
        resp = client_a.get(reverse("hrm:expensecategory_list"), {"q": "Nonexistent Zzz"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert category_a.pk not in pks

    def test_filter_by_is_active(self, client_a, category_a, category_no_limits_a):
        category_no_limits_a.is_active = False
        category_no_limits_a.save(update_fields=["is_active"])
        resp = client_a.get(reverse("hrm:expensecategory_list"), {"is_active": "False"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert category_no_limits_a.pk in pks
        assert category_a.pk not in pks

    def test_bad_page_no_500(self, client_a, category_a):
        resp = client_a.get(reverse("hrm:expensecategory_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_non_admin_can_view(self, member_client, category_a):
        resp = member_client.get(reverse("hrm:expensecategory_list"))
        assert resp.status_code == 200


class TestExpenseCategoryCreateView:
    def test_admin_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:expensecategory_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_admin_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import ExpenseCategory
        resp = client_a.post(reverse("hrm:expensecategory_create"), _category_payload(name="Meals"))
        assert resp.status_code == 302
        obj = ExpenseCategory.objects.get(tenant=tenant_a, name="Meals")
        assert obj.tenant_id == tenant_a.pk

    def test_non_admin_get_forbidden(self, member_client):
        resp = member_client.get(reverse("hrm:expensecategory_create"))
        assert resp.status_code == 403

    def test_non_admin_post_forbidden(self, member_client):
        from apps.hrm.models import ExpenseCategory
        resp = member_client.post(reverse("hrm:expensecategory_create"), _category_payload(name="Blocked"))
        assert resp.status_code == 403
        assert not ExpenseCategory.objects.filter(name="Blocked").exists()

    def test_anonymous_redirected(self, client):
        resp = client.get(reverse("hrm:expensecategory_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestExpenseCategoryEditView:
    def test_admin_get_200(self, client_a, category_a):
        resp = client_a.get(reverse("hrm:expensecategory_edit", args=[category_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_admin_post_updates(self, client_a, category_a):
        resp = client_a.post(reverse("hrm:expensecategory_edit", args=[category_a.pk]),
                              _category_payload(name="Travel Renamed"))
        assert resp.status_code == 302
        category_a.refresh_from_db()
        assert category_a.name == "Travel Renamed"

    def test_non_admin_forbidden(self, member_client, category_a):
        resp = member_client.post(reverse("hrm:expensecategory_edit", args=[category_a.pk]),
                                   _category_payload(name="Hacked"))
        assert resp.status_code == 403
        category_a.refresh_from_db()
        assert category_a.name != "Hacked"


class TestExpenseCategoryDeleteView:
    def test_get_not_allowed(self, client_a, category_a):
        resp = client_a.get(reverse("hrm:expensecategory_delete", args=[category_a.pk]))
        assert resp.status_code == 405

    def test_deletes_unused_category(self, client_a, category_no_limits_a):
        from apps.hrm.models import ExpenseCategory
        pk = category_no_limits_a.pk
        resp = client_a.post(reverse("hrm:expensecategory_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ExpenseCategory.objects.filter(pk=pk).exists()

    def test_blocks_delete_of_used_category(self, client_a, category_a, line_a):
        from apps.hrm.models import ExpenseCategory
        resp = client_a.post(reverse("hrm:expensecategory_delete", args=[category_a.pk]))
        assert resp.status_code == 302
        assert ExpenseCategory.objects.filter(pk=category_a.pk).exists()

    def test_non_admin_forbidden(self, member_client, category_no_limits_a):
        from apps.hrm.models import ExpenseCategory
        resp = member_client.post(reverse("hrm:expensecategory_delete", args=[category_no_limits_a.pk]))
        assert resp.status_code == 403
        assert ExpenseCategory.objects.filter(pk=category_no_limits_a.pk).exists()

    def test_enforces_csrf(self, admin_user, category_no_limits_a):
        from apps.hrm.models import ExpenseCategory
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:expensecategory_delete", args=[category_no_limits_a.pk]))
        assert resp.status_code == 403
        assert ExpenseCategory.objects.filter(pk=category_no_limits_a.pk).exists()


class TestExpenseCategoryDetailView:
    def test_200_with_line_count(self, client_a, category_a, line_a):
        resp = client_a.get(reverse("hrm:expensecategory_detail", args=[category_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == category_a.pk
        assert resp.context["line_count"] == 1


# ============================================================
# 5. ExpenseClaim CRUD + own-vs-admin scoping
# ============================================================

class TestExpenseClaimListView:
    def test_200(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_list"))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/expenses/expenseclaim/list.html"

    def test_context_keys(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_list"))
        for key in ("object_list", "page_obj", "q", "status_choices", "is_admin", "employees"):
            assert key in resp.context

    def test_search_by_title(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_list"), {"q": "Client Site"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk in pks

    def test_search_by_number(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_list"), {"q": draft_claim_a.number})
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk in pks

    def test_filter_by_status(self, client_a, draft_claim_a, submitted_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_list"), {"status": "submitted"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert submitted_claim_a.pk in pks
        assert draft_claim_a.pk not in pks

    def test_filter_by_employee_admin_only(self, client_a, draft_claim_a, tenant_a, employee_a2):
        from apps.hrm.models import ExpenseClaim
        other = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a2, title="Other Emp")
        resp = client_a.get(reverse("hrm:expenseclaim_list"), {"employee": str(draft_claim_a.employee_id)})
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk in pks
        assert other.pk not in pks

    def test_bad_page_no_500(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_non_admin_can_view(self, member_client):
        resp = member_client.get(reverse("hrm:expenseclaim_list"))
        assert resp.status_code == 200


class TestOwnVsAdminScoping:
    def test_own_client_sees_only_own_claims(self, own_client, draft_claim_a, tenant_a, employee_a2):
        from apps.hrm.models import ExpenseClaim
        other_claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a2, title="Not Mine")
        resp = own_client.get(reverse("hrm:expenseclaim_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk in pks
        assert other_claim.pk not in pks

    def test_other_employee_client_cannot_see_draft_claim_a(self, other_employee_client, draft_claim_a):
        resp = other_employee_client.get(reverse("hrm:expenseclaim_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk not in pks

    def test_other_employee_client_detail_403(self, other_employee_client, draft_claim_a):
        resp = other_employee_client.get(reverse("hrm:expenseclaim_detail", args=[draft_claim_a.pk]))
        assert resp.status_code == 403

    def test_other_employee_client_edit_403(self, other_employee_client, draft_claim_a):
        resp = other_employee_client.get(reverse("hrm:expenseclaim_edit", args=[draft_claim_a.pk]))
        assert resp.status_code == 403

    def test_admin_sees_all_claims(self, client_a, draft_claim_a, tenant_a, employee_a2):
        from apps.hrm.models import ExpenseClaim
        other_claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a2, title="Someone Else's")
        resp = client_a.get(reverse("hrm:expenseclaim_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk in pks
        assert other_claim.pk in pks

    def test_admin_can_view_any_claim(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_detail", args=[draft_claim_a.pk]))
        assert resp.status_code == 200

    def test_employee_less_non_admin_sees_no_claims(self, member_client, draft_claim_a):
        resp = member_client.get(reverse("hrm:expenseclaim_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert draft_claim_a.pk not in pks

    def test_employee_less_non_admin_detail_403(self, member_client, draft_claim_a):
        resp = member_client.get(reverse("hrm:expenseclaim_detail", args=[draft_claim_a.pk]))
        assert resp.status_code == 403


class TestExpenseClaimCreateView:
    def test_owner_get_200(self, own_client):
        resp = own_client.get(reverse("hrm:expenseclaim_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_owner_post_creates_for_self(self, own_client, tenant_a, employee_a):
        from apps.hrm.models import ExpenseClaim
        resp = own_client.post(reverse("hrm:expenseclaim_create"), _claim_payload(title="My Own Trip"))
        assert resp.status_code == 302
        obj = ExpenseClaim.objects.get(tenant=tenant_a, title="My Own Trip")
        assert obj.employee_id == employee_a.pk
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("ECL-")

    def test_admin_post_with_employee_pk_creates_for_target(self, client_a, tenant_a, employee_a2):
        from apps.hrm.models import ExpenseClaim
        resp = client_a.post(reverse("hrm:expenseclaim_create"),
                              _claim_payload(title="Admin Assigned Trip", employee_pk=str(employee_a2.pk)))
        assert resp.status_code == 302
        obj = ExpenseClaim.objects.get(tenant=tenant_a, title="Admin Assigned Trip")
        assert obj.employee_id == employee_a2.pk

    def test_admin_post_without_employee_pk_creates_nothing(self, client_a, tenant_a):
        from apps.hrm.models import ExpenseClaim
        resp = client_a.post(reverse("hrm:expenseclaim_create"), _claim_payload(title="Orphan Trip"))
        assert resp.status_code == 302
        assert not ExpenseClaim.objects.filter(tenant=tenant_a, title="Orphan Trip").exists()

    def test_employee_less_non_admin_post_creates_nothing(self, member_client, tenant_a):
        from apps.hrm.models import ExpenseClaim
        resp = member_client.post(reverse("hrm:expenseclaim_create"), _claim_payload(title="No Profile Trip"))
        assert resp.status_code == 302
        assert not ExpenseClaim.objects.filter(tenant=tenant_a, title="No Profile Trip").exists()

    def test_invalid_payload_rerenders_form(self, own_client):
        resp = own_client.post(
            reverse("hrm:expenseclaim_create"),
            _claim_payload(period_start="2026-07-10", period_end="2026-07-01"))
        assert resp.status_code == 200
        assert resp.context["form"].errors


class TestExpenseClaimEditView:
    def test_owner_get_200(self, own_client, draft_claim_a):
        resp = own_client.get(reverse("hrm:expenseclaim_edit", args=[draft_claim_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_owner_post_updates(self, own_client, draft_claim_a):
        resp = own_client.post(reverse("hrm:expenseclaim_edit", args=[draft_claim_a.pk]),
                                _claim_payload(title="Updated Title"))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.title == "Updated Title"

    def test_admin_post_updates(self, client_a, draft_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_edit", args=[draft_claim_a.pk]),
                              _claim_payload(title="Admin Updated"))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.title == "Admin Updated"


class TestExpenseClaimDeleteView:
    def test_get_not_allowed(self, client_a, draft_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_delete", args=[draft_claim_a.pk]))
        assert resp.status_code == 405

    def test_owner_deletes_own_draft(self, own_client, draft_claim_a):
        from apps.hrm.models import ExpenseClaim
        pk = draft_claim_a.pk
        resp = own_client.post(reverse("hrm:expenseclaim_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ExpenseClaim.objects.filter(pk=pk).exists()

    def test_non_owner_non_admin_forbidden(self, other_employee_client, draft_claim_a):
        from apps.hrm.models import ExpenseClaim
        resp = other_employee_client.post(reverse("hrm:expenseclaim_delete", args=[draft_claim_a.pk]))
        assert resp.status_code == 403
        assert ExpenseClaim.objects.filter(pk=draft_claim_a.pk).exists()


class TestExpenseClaimDetailView:
    def test_200_with_context(self, client_a, draft_claim_a, line_a):
        from apps.hrm.models import ExpenseClaim
        resp = client_a.get(reverse("hrm:expenseclaim_detail", args=[draft_claim_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == draft_claim_a.pk
        assert [l.pk for l in resp.context["lines"]] == [line_a.pk]
        assert resp.context["is_admin"] is True
        assert resp.context["line_form"] is not None
        assert resp.context["payment_method_choices"] == ExpenseClaim.PAYMENT_METHOD_CHOICES

    def test_line_form_none_when_not_draft(self, client_a, submitted_claim_a):
        resp = client_a.get(reverse("hrm:expenseclaim_detail", args=[submitted_claim_a.pk]))
        assert resp.context["line_form"] is None


# ============================================================
# 6. Draft-only editing
# ============================================================

class TestDraftOnlyEditing:
    def test_claim_edit_blocked_when_not_draft(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_edit", args=[submitted_claim_a.pk]),
                              _claim_payload(title="Hacked Title"))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.title != "Hacked Title"

    def test_claim_delete_blocked_when_not_draft(self, client_a, submitted_claim_a):
        from apps.hrm.models import ExpenseClaim
        pk = submitted_claim_a.pk
        resp = client_a.post(reverse("hrm:expenseclaim_delete", args=[pk]))
        assert resp.status_code == 302
        assert ExpenseClaim.objects.filter(pk=pk).exists()

    def test_line_add_blocked_when_not_draft(self, client_a, submitted_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        before = ExpenseClaimLine.objects.filter(claim=submitted_claim_a).count()
        resp = client_a.post(reverse("hrm:expenseclaimline_add", args=[submitted_claim_a.pk]),
                              _line_payload(category_a.pk))
        assert resp.status_code == 302
        assert ExpenseClaimLine.objects.filter(claim=submitted_claim_a).count() == before

    def test_line_edit_blocked_when_not_draft(self, client_a, submitted_claim_a):
        line = submitted_claim_a.lines.first()
        original_amount = line.amount
        resp = client_a.post(reverse("hrm:expenseclaimline_edit", args=[line.pk]),
                              _line_payload(line.category_id, amount="999.00"))
        assert resp.status_code == 302
        line.refresh_from_db()
        assert line.amount == original_amount

    def test_line_delete_blocked_when_not_draft(self, client_a, submitted_claim_a):
        from apps.hrm.models import ExpenseClaimLine
        line = submitted_claim_a.lines.first()
        resp = client_a.post(reverse("hrm:expenseclaimline_delete", args=[line.pk]))
        assert resp.status_code == 302
        assert ExpenseClaimLine.objects.filter(pk=line.pk).exists()


# ============================================================
# 7. Inline ExpenseClaimLine CRUD (draft claims)
# ============================================================

class TestExpenseClaimLineCRUD:
    def test_add_line_success(self, client_a, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        resp = client_a.post(reverse("hrm:expenseclaimline_add", args=[draft_claim_a.pk]),
                              _line_payload(category_a.pk))
        assert resp.status_code == 302
        assert ExpenseClaimLine.objects.filter(claim=draft_claim_a).count() == 1

    def test_add_line_invalid_payload_creates_nothing(self, client_a, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        resp = client_a.post(reverse("hrm:expenseclaimline_add", args=[draft_claim_a.pk]),
                              _line_payload(category_a.pk, amount="0"))
        assert resp.status_code == 302
        assert not ExpenseClaimLine.objects.filter(claim=draft_claim_a).exists()

    def test_add_line_by_owner(self, own_client, draft_claim_a, category_a):
        from apps.hrm.models import ExpenseClaimLine
        resp = own_client.post(reverse("hrm:expenseclaimline_add", args=[draft_claim_a.pk]),
                                _line_payload(category_a.pk))
        assert resp.status_code == 302
        assert ExpenseClaimLine.objects.filter(claim=draft_claim_a).exists()

    def test_add_line_by_non_owner_forbidden(self, other_employee_client, draft_claim_a, category_a):
        resp = other_employee_client.post(reverse("hrm:expenseclaimline_add", args=[draft_claim_a.pk]),
                                           _line_payload(category_a.pk))
        assert resp.status_code == 403

    def test_edit_line_get_200(self, client_a, line_a):
        resp = client_a.get(reverse("hrm:expenseclaimline_edit", args=[line_a.pk]))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/expenses/expenseclaimline/form.html"
        assert resp.context["is_edit"] is True

    def test_edit_line_post_updates(self, client_a, line_a):
        resp = client_a.post(reverse("hrm:expenseclaimline_edit", args=[line_a.pk]),
                              _line_payload(line_a.category_id, amount="123.45"))
        assert resp.status_code == 302
        line_a.refresh_from_db()
        assert line_a.amount == Decimal("123.45")

    def test_edit_line_by_non_owner_forbidden(self, other_employee_client, line_a):
        resp = other_employee_client.get(reverse("hrm:expenseclaimline_edit", args=[line_a.pk]))
        assert resp.status_code == 403

    def test_delete_line_success(self, client_a, line_a):
        from apps.hrm.models import ExpenseClaimLine
        pk = line_a.pk
        resp = client_a.post(reverse("hrm:expenseclaimline_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ExpenseClaimLine.objects.filter(pk=pk).exists()

    def test_delete_line_get_not_allowed(self, client_a, line_a):
        resp = client_a.get(reverse("hrm:expenseclaimline_delete", args=[line_a.pk]))
        assert resp.status_code == 405

    def test_delete_line_by_non_owner_forbidden(self, other_employee_client, line_a):
        from apps.hrm.models import ExpenseClaimLine
        resp = other_employee_client.post(reverse("hrm:expenseclaimline_delete", args=[line_a.pk]))
        assert resp.status_code == 403
        assert ExpenseClaimLine.objects.filter(pk=line_a.pk).exists()


# ============================================================
# 8. The 2-stage workflow
# ============================================================

class TestExpenseClaimSubmit:
    def test_zero_lines_rejected(self, client_a, draft_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_submit", args=[draft_claim_a.pk]))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "draft"

    def test_with_line_succeeds(self, client_a, draft_claim_a, line_a):
        resp = client_a.post(reverse("hrm:expenseclaim_submit", args=[draft_claim_a.pk]))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "submitted"

    def test_non_draft_rejected(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_submit", args=[submitted_claim_a.pk]))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "submitted"

    def test_owner_can_submit(self, own_client, draft_claim_a, line_a):
        resp = own_client.post(reverse("hrm:expenseclaim_submit", args=[draft_claim_a.pk]))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "submitted"

    def test_non_owner_non_admin_forbidden(self, other_employee_client, draft_claim_a, line_a):
        resp = other_employee_client.post(reverse("hrm:expenseclaim_submit", args=[draft_claim_a.pk]))
        assert resp.status_code == 403
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "draft"


class TestExpenseClaimManagerApprove:
    def test_success(self, client_a, submitted_claim_a, admin_user):
        resp = client_a.post(reverse("hrm:expenseclaim_manager_approve", args=[submitted_claim_a.pk]))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "manager_approved"
        assert submitted_claim_a.manager_approver_id == admin_user.pk
        assert submitted_claim_a.manager_approved_at is not None

    def test_from_draft_rejected(self, client_a, draft_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_manager_approve", args=[draft_claim_a.pk]))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "draft"

    def test_from_manager_approved_rejected(self, client_a, manager_approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_manager_approve", args=[manager_approved_claim_a.pk]))
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "manager_approved"

    def test_non_admin_forbidden(self, member_client, submitted_claim_a):
        resp = member_client.post(reverse("hrm:expenseclaim_manager_approve", args=[submitted_claim_a.pk]))
        assert resp.status_code == 403


class TestExpenseClaimApprove:
    def test_success(self, client_a, manager_approved_claim_a, admin_user):
        resp = client_a.post(reverse("hrm:expenseclaim_approve", args=[manager_approved_claim_a.pk]))
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "approved"
        assert manager_approved_claim_a.finance_approver_id == admin_user.pk
        assert manager_approved_claim_a.approved_at is not None

    def test_directly_from_submitted_rejected(self, client_a, submitted_claim_a):
        """The stage cannot be skipped: approve() requires manager_approved, not submitted."""
        resp = client_a.post(reverse("hrm:expenseclaim_approve", args=[submitted_claim_a.pk]))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "submitted"

    def test_non_admin_forbidden(self, member_client, manager_approved_claim_a):
        resp = member_client.post(reverse("hrm:expenseclaim_approve", args=[manager_approved_claim_a.pk]))
        assert resp.status_code == 403


class TestExpenseClaimReject:
    def test_missing_reason_rejected(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[submitted_claim_a.pk]), {})
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "submitted"

    def test_blank_reason_rejected(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[submitted_claim_a.pk]),
                              {"rejection_reason": "   "})
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "submitted"

    def test_from_draft_rejected(self, client_a, draft_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[draft_claim_a.pk]),
                              {"rejection_reason": "not eligible"})
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "draft"

    def test_from_approved_rejected(self, client_a, approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[approved_claim_a.pk]),
                              {"rejection_reason": "too late"})
        assert resp.status_code == 302
        approved_claim_a.refresh_from_db()
        assert approved_claim_a.status == "approved"

    def test_from_submitted_stamps_manager_pair(self, client_a, submitted_claim_a, admin_user):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[submitted_claim_a.pk]),
                              {"rejection_reason": "Missing documentation"})
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "rejected"
        assert submitted_claim_a.manager_approver_id == admin_user.pk
        assert submitted_claim_a.manager_approved_at is not None
        assert submitted_claim_a.finance_approver_id is None
        assert submitted_claim_a.approved_at is None
        assert submitted_claim_a.rejection_reason == "Missing documentation"

    def test_from_manager_approved_stamps_finance_pair(self, client_a, manager_approved_claim_a, admin_user):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[manager_approved_claim_a.pk]),
                              {"rejection_reason": "Policy violation"})
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "rejected"
        assert manager_approved_claim_a.finance_approver_id == admin_user.pk
        assert manager_approved_claim_a.approved_at is not None
        assert manager_approved_claim_a.rejection_reason == "Policy violation"

    def test_non_admin_forbidden(self, member_client, submitted_claim_a):
        resp = member_client.post(reverse("hrm:expenseclaim_reject", args=[submitted_claim_a.pk]),
                                   {"rejection_reason": "nope"})
        assert resp.status_code == 403


class TestExpenseClaimCancel:
    def test_cancel_from_draft(self, client_a, draft_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_cancel", args=[draft_claim_a.pk]))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "cancelled"

    def test_cancel_from_submitted(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_cancel", args=[submitted_claim_a.pk]))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "cancelled"

    def test_cancel_from_manager_approved_rejected(self, client_a, manager_approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_cancel", args=[manager_approved_claim_a.pk]))
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "manager_approved"

    def test_owner_can_cancel(self, own_client, draft_claim_a):
        resp = own_client.post(reverse("hrm:expenseclaim_cancel", args=[draft_claim_a.pk]))
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "cancelled"

    def test_non_owner_non_admin_forbidden(self, other_employee_client, draft_claim_a):
        resp = other_employee_client.post(reverse("hrm:expenseclaim_cancel", args=[draft_claim_a.pk]))
        assert resp.status_code == 403

    def test_enforces_csrf(self, admin_user, draft_claim_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:expenseclaim_cancel", args=[draft_claim_a.pk]))
        assert resp.status_code == 403
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "draft"


class TestExpenseClaimReimburse:
    def test_success(self, client_a, approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reimburse", args=[approved_claim_a.pk]),
                              {"payment_method": "bank_transfer", "payment_reference": "TXN123"})
        assert resp.status_code == 302
        approved_claim_a.refresh_from_db()
        assert approved_claim_a.status == "reimbursed"
        assert approved_claim_a.payment_method == "bank_transfer"
        assert approved_claim_a.payment_reference == "TXN123"
        assert approved_claim_a.reimbursed_at is not None

    def test_invalid_payment_method_rejected(self, client_a, approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reimburse", args=[approved_claim_a.pk]),
                              {"payment_method": "bitcoin"})
        assert resp.status_code == 302
        approved_claim_a.refresh_from_db()
        assert approved_claim_a.status == "approved"

    def test_missing_payment_method_rejected(self, client_a, approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reimburse", args=[approved_claim_a.pk]), {})
        assert resp.status_code == 302
        approved_claim_a.refresh_from_db()
        assert approved_claim_a.status == "approved"

    def test_draft_claim_rejected(self, client_a, draft_claim_a):
        """The stage cannot be skipped: reimburse() requires approved, not draft."""
        resp = client_a.post(reverse("hrm:expenseclaim_reimburse", args=[draft_claim_a.pk]),
                              {"payment_method": "cash"})
        assert resp.status_code == 302
        draft_claim_a.refresh_from_db()
        assert draft_claim_a.status == "draft"

    def test_manager_approved_claim_rejected(self, client_a, manager_approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reimburse", args=[manager_approved_claim_a.pk]),
                              {"payment_method": "cash"})
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "manager_approved"

    def test_non_admin_forbidden(self, member_client, approved_claim_a):
        resp = member_client.post(reverse("hrm:expenseclaim_reimburse", args=[approved_claim_a.pk]),
                                   {"payment_method": "cash"})
        assert resp.status_code == 403


# ============================================================
# 9. Self-approval block
# ============================================================

class TestSelfApprovalBlock:
    def test_manager_approve_own_blocked(self, self_admin_client, submitted_claim_a):
        resp = self_admin_client.post(reverse("hrm:expenseclaim_manager_approve", args=[submitted_claim_a.pk]))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "submitted"

    def test_manager_approve_different_admin_allowed(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_manager_approve", args=[submitted_claim_a.pk]))
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "manager_approved"

    def test_approve_own_blocked(self, self_admin_client, manager_approved_claim_a):
        resp = self_admin_client.post(reverse("hrm:expenseclaim_approve", args=[manager_approved_claim_a.pk]))
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "manager_approved"

    def test_approve_different_admin_allowed(self, client_a, manager_approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_approve", args=[manager_approved_claim_a.pk]))
        assert resp.status_code == 302
        manager_approved_claim_a.refresh_from_db()
        assert manager_approved_claim_a.status == "approved"

    def test_reject_own_blocked(self, self_admin_client, submitted_claim_a):
        resp = self_admin_client.post(reverse("hrm:expenseclaim_reject", args=[submitted_claim_a.pk]),
                                       {"rejection_reason": "self trying to reject"})
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "submitted"

    def test_reject_different_admin_allowed(self, client_a, submitted_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reject", args=[submitted_claim_a.pk]),
                              {"rejection_reason": "Missing receipts"})
        assert resp.status_code == 302
        submitted_claim_a.refresh_from_db()
        assert submitted_claim_a.status == "rejected"

    def test_reimburse_own_blocked(self, self_admin_client, approved_claim_a):
        """The reimburse self-approval guard — an admin who is ALSO the claim's employee cannot
        mark their own approved claim reimbursed."""
        resp = self_admin_client.post(reverse("hrm:expenseclaim_reimburse", args=[approved_claim_a.pk]),
                                       {"payment_method": "bank_transfer"})
        assert resp.status_code == 302
        approved_claim_a.refresh_from_db()
        assert approved_claim_a.status == "approved"

    def test_reimburse_different_admin_allowed(self, client_a, approved_claim_a):
        resp = client_a.post(reverse("hrm:expenseclaim_reimburse", args=[approved_claim_a.pk]),
                              {"payment_method": "cash"})
        assert resp.status_code == 302
        approved_claim_a.refresh_from_db()
        assert approved_claim_a.status == "reimbursed"


# ============================================================
# 10. Multi-tenant isolation / IDOR
# ============================================================

class TestMultiTenantIsolation:
    def test_category_detail_404_cross_tenant(self, client_a, category_b):
        resp = client_a.get(reverse("hrm:expensecategory_detail", args=[category_b.pk]))
        assert resp.status_code == 404

    def test_category_edit_404_cross_tenant(self, client_a, category_b):
        resp = client_a.get(reverse("hrm:expensecategory_edit", args=[category_b.pk]))
        assert resp.status_code == 404

    def test_category_delete_404_cross_tenant(self, client_a, category_b):
        from apps.hrm.models import ExpenseCategory
        resp = client_a.post(reverse("hrm:expensecategory_delete", args=[category_b.pk]))
        assert resp.status_code == 404
        assert ExpenseCategory.objects.filter(pk=category_b.pk).exists()

    def test_category_list_excludes_other_tenant(self, client_a, category_b):
        resp = client_a.get(reverse("hrm:expensecategory_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert category_b.pk not in pks

    def test_claim_detail_404_cross_tenant(self, client_a, claim_b):
        resp = client_a.get(reverse("hrm:expenseclaim_detail", args=[claim_b.pk]))
        assert resp.status_code == 404

    def test_claim_edit_404_cross_tenant(self, client_a, claim_b):
        resp = client_a.get(reverse("hrm:expenseclaim_edit", args=[claim_b.pk]))
        assert resp.status_code == 404

    def test_claim_delete_404_cross_tenant(self, client_a, claim_b):
        from apps.hrm.models import ExpenseClaim
        resp = client_a.post(reverse("hrm:expenseclaim_delete", args=[claim_b.pk]))
        assert resp.status_code == 404
        assert ExpenseClaim.objects.filter(pk=claim_b.pk).exists()

    @pytest.mark.parametrize("url_name", [
        "expenseclaim_submit", "expenseclaim_manager_approve", "expenseclaim_approve",
        "expenseclaim_reject", "expenseclaim_cancel", "expenseclaim_reimburse",
    ])
    def test_claim_workflow_actions_404_cross_tenant(self, client_a, claim_b, url_name):
        resp = client_a.post(reverse(f"hrm:{url_name}", args=[claim_b.pk]))
        assert resp.status_code == 404

    def test_claim_list_excludes_other_tenant(self, client_a, claim_b):
        resp = client_a.get(reverse("hrm:expenseclaim_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert claim_b.pk not in pks

    def test_line_edit_404_cross_tenant(self, client_a, line_b):
        resp = client_a.get(reverse("hrm:expenseclaimline_edit", args=[line_b.pk]))
        assert resp.status_code == 404

    def test_line_delete_404_cross_tenant(self, client_a, line_b):
        from apps.hrm.models import ExpenseClaimLine
        resp = client_a.post(reverse("hrm:expenseclaimline_delete", args=[line_b.pk]))
        assert resp.status_code == 404
        assert ExpenseClaimLine.objects.filter(pk=line_b.pk).exists()

    def test_line_add_404_cross_tenant_claim(self, client_a, claim_b, category_a):
        resp = client_a.post(reverse("hrm:expenseclaimline_add", args=[claim_b.pk]),
                              _line_payload(category_a.pk))
        assert resp.status_code == 404


# ============================================================
# 11. Anonymous access
# ============================================================

class TestAnonymousAccess:
    @pytest.mark.parametrize("url_name", [
        "hrm:expensecategory_list", "hrm:expensecategory_create",
        "hrm:expenseclaim_list", "hrm:expenseclaim_create",
    ])
    def test_anon_redirected(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_and_edit(self, client, draft_claim_a, category_a):
        for url_name, pk in [
            ("hrm:expensecategory_detail", category_a.pk),
            ("hrm:expensecategory_edit", category_a.pk),
            ("hrm:expenseclaim_detail", draft_claim_a.pk),
            ("hrm:expenseclaim_edit", draft_claim_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only(self, client, draft_claim_a, category_a):
        for url_name, pk in [
            ("hrm:expensecategory_delete", category_a.pk),
            ("hrm:expenseclaim_delete", draft_claim_a.pk),
            ("hrm:expenseclaim_submit", draft_claim_a.pk),
            ("hrm:expenseclaim_cancel", draft_claim_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ============================================================
# 12. Query-count ceiling (N+1 guard)
# ============================================================

class TestExpenseClaimListQueryCount:
    def test_query_count_bounded(self, client_a, many_claims_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:expenseclaim_list"))

    def test_query_count_does_not_grow_with_claim_count(self, client_a, tenant_a, employee_a, category_a):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        from apps.hrm.models import ExpenseClaim, ExpenseClaimLine

        def _make_claims(n, start):
            for i in range(start, start + n):
                claim = ExpenseClaim.objects.create(tenant=tenant_a, employee=employee_a, title=f"C{i}")
                ExpenseClaimLine.objects.create(
                    tenant=tenant_a, claim=claim, category=category_a,
                    expense_date=datetime.date(2026, 7, 1), amount=Decimal("40.00"))
                ExpenseClaimLine.objects.create(
                    tenant=tenant_a, claim=claim, category=category_a,
                    expense_date=datetime.date(2026, 7, 2), amount=Decimal("60.00"))

        _make_claims(2, 0)
        with CaptureQueriesContext(connection) as small_ctx:
            resp = client_a.get(reverse("hrm:expenseclaim_list"))
        assert resp.status_code == 200
        small_count = len(small_ctx.captured_queries)

        _make_claims(10, 2)
        with CaptureQueriesContext(connection) as large_ctx:
            resp = client_a.get(reverse("hrm:expenseclaim_list"))
        assert resp.status_code == 200
        large_count = len(large_ctx.captured_queries)

        assert large_count == small_count
