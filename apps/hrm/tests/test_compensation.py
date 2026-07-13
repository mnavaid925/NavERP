"""Tests for HRM 3.37 Compensation & Benefits: ``SalaryBenchmark`` (compa-ratio) + ``BenefitPlan``
(catalog + tier_list) + ``EmployeeBenefitEnrollment`` (``BEN-``, own-vs-admin election + enroll/waive/
terminate) + ``EquityGrant`` (``ESOP-``, computed cliff/graded vesting + record-exercise).

Mirrors test_helpdesk.py fixture style. Covers auto-numbers, the computed vesting/compa-ratio properties,
CRUD, the admin lifecycle actions, the record-exercise over-exercise guard, the benefit-plan delete guard,
own-vs-admin scoping + cross-employee IDOR (403), multi-tenant IDOR (404), and non-admin write blocks (403).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


def _client_for(party, tenant, *, email, username, is_admin=False):
    from apps.accounts.models import User
    user = User.objects.create_user(email=email, username=username, password="TestPass123!",
                                    tenant=tenant, is_tenant_admin=is_admin)
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def own_client(tenant_a, employee_a):
    return _client_for(employee_a.party, tenant_a, email="owner@acme.com", username="owner_acme")


@pytest.fixture
def other_employee_client(tenant_a, employee_a2):
    return _client_for(employee_a2.party, tenant_a, email="other@acme.com", username="other_acme")


@pytest.fixture
def benchmark_a(db, tenant_a, designation_a):
    from apps.hrm.models import SalaryBenchmark
    return SalaryBenchmark.objects.create(
        tenant=tenant_a, source="payscale", region="US-National", designation=designation_a,
        percentile_25=Decimal("70000"), percentile_50=Decimal("85000"),
        percentile_75=Decimal("100000"), percentile_90=Decimal("120000"), survey_date=TODAY)


@pytest.fixture
def plan_a(db, tenant_a):
    from apps.hrm.models import BenefitPlan
    return BenefitPlan.objects.create(
        tenant=tenant_a, name="Premium Medical", plan_type="medical", provider="BlueCross",
        employer_cost_monthly=Decimal("400"), employee_cost_monthly=Decimal("120"),
        coverage_tier_options="employee_only,family", is_active=True)


@pytest.fixture
def enrollment_a(db, tenant_a, employee_a, plan_a):
    from apps.hrm.models import EmployeeBenefitEnrollment
    return EmployeeBenefitEnrollment.objects.create(
        tenant=tenant_a, employee=employee_a, plan=plan_a, election_choice="opt_in",
        coverage_tier="family", effective_from=TODAY, status="pending")


@pytest.fixture
def grant_a(db, tenant_a, employee_a):
    """A monthly-vesting RSU whose vesting started 18 months ago — partially vested (past the 12-mo cliff)."""
    from apps.hrm.models import EquityGrant
    start = TODAY - datetime.timedelta(days=550)
    return EquityGrant.objects.create(
        tenant=tenant_a, employee=employee_a, grant_type="rsu", grant_date=start, shares_granted=4800,
        vesting_start_date=start, cliff_months=12, vesting_duration_months=48, vesting_frequency="monthly",
        status="active")


# ---- tenant_b (IDOR) ----
@pytest.fixture
def plan_b(db, tenant_b):
    from apps.hrm.models import BenefitPlan
    return BenefitPlan.objects.create(tenant=tenant_b, name="Plan B", plan_type="dental")


@pytest.fixture
def enrollment_b(db, tenant_b, employee_b, plan_b):
    from apps.hrm.models import EmployeeBenefitEnrollment
    return EmployeeBenefitEnrollment.objects.create(
        tenant=tenant_b, employee=employee_b, plan=plan_b, effective_from=TODAY, status="pending")


@pytest.fixture
def grant_b(db, tenant_b, employee_b):
    from apps.hrm.models import EquityGrant
    return EquityGrant.objects.create(
        tenant=tenant_b, employee=employee_b, grant_type="iso", grant_date=TODAY, shares_granted=1000,
        vesting_start_date=TODAY, cliff_months=12, vesting_duration_months=48)


# ============================================================ Models
def test_compa_ratio(benchmark_a):
    assert benchmark_a.compa_ratio(Decimal("85000")) == Decimal("1.00")
    assert benchmark_a.compa_ratio(Decimal("93500")) == Decimal("1.10")
    assert benchmark_a.compa_ratio(None) is None


def test_benefitplan_tier_list(plan_a):
    assert plan_a.tier_list == ["employee_only", "family"]


def test_enrollment_autonumber(enrollment_a):
    assert enrollment_a.number.startswith("BEN-")
    assert enrollment_a.is_open is True


def test_grant_autonumber(grant_a):
    assert grant_a.number.startswith("ESOP-")


def test_grant_partial_vesting(grant_a):
    # ~18 months elapsed of a 48-month monthly schedule → between 25% and 50% vested, not full.
    assert 0 < grant_a.vested_shares < grant_a.shares_granted
    assert Decimal("25") <= grant_a.vested_percent <= Decimal("50")
    assert grant_a.exercisable_shares == grant_a.vested_shares  # none exercised yet
    assert grant_a.unvested_shares == grant_a.shares_granted - grant_a.vested_shares


def test_grant_pre_cliff_zero(tenant_a, employee_a):
    from apps.hrm.models import EquityGrant
    g = EquityGrant.objects.create(
        tenant=tenant_a, employee=employee_a, grant_type="rsu", grant_date=TODAY, shares_granted=1000,
        vesting_start_date=TODAY, cliff_months=12, vesting_duration_months=48)
    assert g.vested_shares == 0  # before the cliff


def test_grant_fully_vested(tenant_a, employee_a):
    from apps.hrm.models import EquityGrant
    start = TODAY - datetime.timedelta(days=5 * 365)
    g = EquityGrant.objects.create(
        tenant=tenant_a, employee=employee_a, grant_type="rsu", grant_date=start, shares_granted=1000,
        vesting_start_date=start, cliff_months=12, vesting_duration_months=48)
    assert g.vested_shares == 1000
    assert g.vested_percent == Decimal("100.00")


# ============================================================ Views / lifecycle
def test_lists_render(client_a, benchmark_a, plan_a, enrollment_a, grant_a):
    for name in ["salarybenchmark_list", "benefitplan_list",
                 "employeebenefitenrollment_list", "equitygrant_list"]:
        assert client_a.get(reverse(f"hrm:{name}")).status_code == 200


def test_full_url_sweep(client_a, benchmark_a, plan_a, enrollment_a, grant_a, employee_a):
    urls = [
        ("hrm:salarybenchmark_detail", [benchmark_a.pk], ""), ("hrm:salarybenchmark_edit", [benchmark_a.pk], ""),
        ("hrm:salarybenchmark_create", [], ""), ("hrm:benefitplan_detail", [plan_a.pk], ""),
        ("hrm:benefitplan_edit", [plan_a.pk], ""), ("hrm:benefitplan_create", [], ""),
        ("hrm:employeebenefitenrollment_detail", [enrollment_a.pk], ""),
        ("hrm:employeebenefitenrollment_edit", [enrollment_a.pk], ""),
        ("hrm:employeebenefitenrollment_create", [], f"?employee={employee_a.pk}"),
        ("hrm:equitygrant_detail", [grant_a.pk], ""), ("hrm:equitygrant_edit", [grant_a.pk], ""),
        ("hrm:equitygrant_create", [], ""),
    ]
    for name, args, qs in urls:
        assert client_a.get(reverse(name, args=args) + qs).status_code == 200, name


def test_benefitplan_create_and_delete_guard(client_a, tenant_a, plan_a, enrollment_a):
    from apps.hrm.models import BenefitPlan
    # create
    resp = client_a.post(reverse("hrm:benefitplan_create"), {
        "name": "Vision Plan", "plan_type": "vision", "provider": "VSP",
        "employer_cost_monthly": "20", "employee_cost_monthly": "5",
        "coverage_tier_options": "employee_only", "is_active": "on"})
    assert resp.status_code == 302
    assert BenefitPlan.objects.filter(tenant=tenant_a, name="Vision Plan").exists()
    # delete guard: plan_a has an enrollment → blocked
    resp = client_a.post(reverse("hrm:benefitplan_delete", args=[plan_a.pk]))
    assert resp.status_code == 302
    assert BenefitPlan.objects.filter(pk=plan_a.pk).exists()


def test_enrollment_create_defaults_contributions(client_a, employee_a, plan_a):
    from apps.hrm.models import EmployeeBenefitEnrollment
    resp = client_a.post(reverse("hrm:employeebenefitenrollment_create"), {
        "plan": plan_a.pk, "election_choice": "opt_in", "coverage_tier": "family",
        "effective_from": TODAY.isoformat(), "employee_pk": employee_a.pk})
    assert resp.status_code == 302
    e = EmployeeBenefitEnrollment.objects.get(tenant=plan_a.tenant, employee=employee_a, plan=plan_a)
    # Blank contributions inherited the plan defaults.
    assert e.employee_contribution == plan_a.employee_cost_monthly
    assert e.employer_contribution == plan_a.employer_cost_monthly


def test_enrollment_lifecycle(client_a, enrollment_a):
    from apps.hrm.models import EmployeeBenefitEnrollment
    client_a.post(reverse("hrm:employeebenefitenrollment_enroll", args=[enrollment_a.pk]))
    e = EmployeeBenefitEnrollment.objects.get(pk=enrollment_a.pk)
    assert e.status == "enrolled" and e.enrolled_at is not None and e.decided_by_id is not None
    client_a.post(reverse("hrm:employeebenefitenrollment_terminate", args=[enrollment_a.pk]))
    e.refresh_from_db()
    assert e.status == "terminated"


def test_record_exercise_and_guard(client_a, grant_a):
    from apps.hrm.models import EquityGrant
    exercisable = grant_a.exercisable_shares
    # over-exercise blocked
    resp = client_a.post(reverse("hrm:equitygrant_record_exercise", args=[grant_a.pk]),
                         {"shares": str(exercisable + 100)})
    assert resp.status_code == 302
    assert EquityGrant.objects.get(pk=grant_a.pk).exercised_shares == 0
    # valid exercise
    client_a.post(reverse("hrm:equitygrant_record_exercise", args=[grant_a.pk]), {"shares": "10"})
    g = EquityGrant.objects.get(pk=grant_a.pk)
    assert g.exercised_shares == 10 and g.last_exercised_at is not None


# ============================================================ Access control + isolation
def test_anonymous_redirected(client, plan_a):
    resp = client.get(reverse("hrm:benefitplan_list"))
    assert resp.status_code == 302 and "/login" in resp.url


def test_non_admin_cannot_create_plan(own_client):
    assert own_client.get(reverse("hrm:benefitplan_create")).status_code == 403


def test_non_admin_cannot_create_grant(own_client):
    assert own_client.get(reverse("hrm:equitygrant_create")).status_code == 403


def test_enrollment_own_scoping(other_employee_client, enrollment_a):
    resp = other_employee_client.get(reverse("hrm:employeebenefitenrollment_list"))
    assert resp.status_code == 200
    assert enrollment_a.number.encode() not in resp.content


def test_grant_cross_employee_idor_403(other_employee_client, grant_a):
    assert other_employee_client.get(reverse("hrm:equitygrant_detail", args=[grant_a.pk])).status_code == 403


def test_multitenant_idor_404(client_a, plan_b, enrollment_b, grant_b):
    assert client_a.get(reverse("hrm:benefitplan_detail", args=[plan_b.pk])).status_code == 404
    assert client_a.get(reverse("hrm:employeebenefitenrollment_detail", args=[enrollment_b.pk])).status_code == 404
    assert client_a.get(reverse("hrm:equitygrant_detail", args=[grant_b.pk])).status_code == 404
