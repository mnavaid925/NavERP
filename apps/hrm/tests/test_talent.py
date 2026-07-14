"""Tests for HRM 3.38 Talent Management & Succession Planning: ``TalentPool`` + ``TalentPoolMembership``
(the COMPUTED 9-box grid + flight risk/retention) + ``SuccessionPlan`` (``SPL-``, computed bench strength)
+ ``SuccessionCandidate`` (ranked inline bench).

CONFIDENTIALITY is the headline property: every 3.38 view is ``@tenant_admin_required`` — a plain employee
must never see who is in a HiPo pool, their 9-box placement, a flight-risk flag, or a succession bench.

Also guards the 3.38 wiring fix: ``jobrequisition_list`` now accepts ``?posting_type=`` so the "Internal
Mobility" sidebar deep-link actually filters (it previously showed every requisition).
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
def employee_client(tenant_a, employee_a):
    """A NON-admin employee — must be locked out of every 3.38 view."""
    return _client_for(employee_a.party, tenant_a, email="emp@acme.com", username="emp_acme")


@pytest.fixture
def pool_a(db, tenant_a, employee_a):
    from apps.hrm.models import TalentPool
    return TalentPool.objects.create(tenant=tenant_a, name="High Potentials", pool_type="hipo",
                                     owner=employee_a)


def _member(tenant, pool, employee, perf=None, pot=None, risk="low", status="active"):
    from apps.hrm.models import TalentPoolMembership
    return TalentPoolMembership.objects.create(
        tenant=tenant, pool=pool, employee=employee, status=status, flight_risk=risk,
        performance_rating=perf, potential_rating=pot, joined_on=TODAY)


@pytest.fixture
def star_a(db, tenant_a, pool_a, employee_a):
    return _member(tenant_a, pool_a, employee_a, Decimal("4.5"), Decimal("4.6"))


@pytest.fixture
def plan_a(db, tenant_a, designation_a, employee_a):
    from apps.hrm.models import SuccessionPlan
    return SuccessionPlan.objects.create(
        tenant=tenant_a, critical_role=designation_a, incumbent=employee_a,
        vacancy_risk="high", status="active", review_date=TODAY)


# ---- tenant_b (IDOR) ----
@pytest.fixture
def pool_b(db, tenant_b):
    from apps.hrm.models import TalentPool
    return TalentPool.objects.create(tenant=tenant_b, name="Pool B", pool_type="hipo")


@pytest.fixture
def plan_b(db, tenant_b, designation_b):
    from apps.hrm.models import SuccessionPlan
    return SuccessionPlan.objects.create(tenant=tenant_b, critical_role=designation_b, status="active")


# ============================================================ Models: the computed 9-box
def test_nine_box_star(star_a):
    assert star_a.performance_band == "high" and star_a.potential_band == "high"
    assert star_a.nine_box_quadrant == "Star"


def test_nine_box_core_player(tenant_a, pool_a, employee_a2):
    m = _member(tenant_a, pool_a, employee_a2, Decimal("3.2"), Decimal("3.3"))
    assert m.nine_box_quadrant == "Core Player"


def test_nine_box_underperformer(tenant_a, pool_a, employee_a2):
    m = _member(tenant_a, pool_a, employee_a2, Decimal("2.0"), Decimal("2.0"))
    assert m.nine_box_quadrant == "Underperformer"


def test_nine_box_unrated_is_none(tenant_a, pool_a, employee_a2):
    m = _member(tenant_a, pool_a, employee_a2)  # no ratings, no review
    assert m.effective_performance is None and m.nine_box_quadrant is None


def test_ratings_fall_back_to_linked_review(tenant_a, pool_a, employee_a2, performance_review_a):
    """With no overrides, the axes come from the linked 3.19 PerformanceReview."""
    from apps.hrm.models import TalentPoolMembership
    performance_review_a.calibrated_rating = Decimal("4.4")   # -> effective_rating
    performance_review_a.potential_rating = Decimal("4.2")
    performance_review_a.save(update_fields=["calibrated_rating", "potential_rating"])
    m = TalentPoolMembership.objects.create(
        tenant=tenant_a, pool=pool_a, employee=employee_a2, review=performance_review_a)
    assert m.effective_performance == Decimal("4.4")
    assert m.effective_potential == Decimal("4.2")
    assert m.nine_box_quadrant == "Star"


def test_override_beats_review(tenant_a, pool_a, employee_a2, performance_review_a):
    from apps.hrm.models import TalentPoolMembership
    performance_review_a.calibrated_rating = Decimal("4.4")
    performance_review_a.save(update_fields=["calibrated_rating"])
    m = TalentPoolMembership.objects.create(
        tenant=tenant_a, pool=pool_a, employee=employee_a2, review=performance_review_a,
        performance_rating=Decimal("2.0"), potential_rating=Decimal("2.0"))
    assert m.effective_performance == Decimal("2.0")  # override wins
    assert m.nine_box_quadrant == "Underperformer"


def test_pool_active_member_count(pool_a, star_a):
    assert pool_a.active_member_count == 1


# ============================================================ Models: succession
def test_plan_autonumber_and_empty_bench(plan_a):
    assert plan_a.number.startswith("SPL-")
    assert plan_a.bench_strength == "none" and plan_a.ready_now_count == 0


def test_bench_strength_progression(tenant_a, plan_a, employee_a, employee_a2):
    from apps.hrm.models import SuccessionCandidate
    SuccessionCandidate.objects.create(tenant=tenant_a, plan=plan_a, candidate=employee_a,
                                       readiness="development_needed", rank_order=1)
    assert plan_a.bench_strength == "weak"          # candidates, none ready
    SuccessionCandidate.objects.create(tenant=tenant_a, plan=plan_a, candidate=employee_a2,
                                       readiness="ready_now", rank_order=2)
    assert plan_a.bench_strength == "moderate"      # exactly 1 ready now
    SuccessionCandidate.objects.filter(plan=plan_a, candidate=employee_a).update(readiness="ready_now")
    assert plan_a.bench_strength == "strong"        # 2+ ready now


# ============================================================ Views (admin)
def test_lists_render(client_a, pool_a, star_a, plan_a):
    for name in ["talentpool_list", "talentpoolmembership_list", "successionplan_list", "talent_nine_box"]:
        assert client_a.get(reverse(f"hrm:{name}")).status_code == 200


def test_nine_box_grid_places_member(client_a, star_a):
    resp = client_a.get(reverse("hrm:talent_nine_box"))
    assert resp.status_code == 200
    assert b"Star" in resp.content
    assert star_a.employee.party.name.encode() in resp.content


def test_talentpool_duplicate_name_shows_form_error(client_a, pool_a):
    """unique_together(tenant, name) — a duplicate must re-render the form (200), not 500."""
    from apps.hrm.models import TalentPool
    before = TalentPool.objects.filter(tenant=pool_a.tenant).count()
    resp = client_a.post(reverse("hrm:talentpool_create"), {
        "name": pool_a.name, "pool_type": "leadership", "is_active": "on"})
    assert resp.status_code == 200
    assert TalentPool.objects.filter(tenant=pool_a.tenant).count() == before


def test_membership_duplicate_shows_form_error(client_a, tenant_a, pool_a, star_a, employee_a):
    """unique_together(tenant, pool, employee) — guarded in clean(), no 500."""
    from apps.hrm.models import TalentPoolMembership
    before = TalentPoolMembership.objects.filter(tenant=tenant_a).count()
    resp = client_a.post(reverse("hrm:talentpoolmembership_create"), {
        "pool": pool_a.pk, "employee": employee_a.pk, "status": "active", "flight_risk": "low"})
    assert resp.status_code == 200
    assert TalentPoolMembership.objects.filter(tenant=tenant_a).count() == before


def test_talentpool_delete_guarded_while_members(client_a, pool_a, star_a):
    from apps.hrm.models import TalentPool
    resp = client_a.post(reverse("hrm:talentpool_delete", args=[pool_a.pk]))
    assert resp.status_code == 302
    assert TalentPool.objects.filter(pk=pool_a.pk).exists()  # blocked


def test_succession_candidate_inline_lifecycle(client_a, plan_a, employee_a2):
    from apps.hrm.models import SuccessionCandidate
    # add
    resp = client_a.post(reverse("hrm:successioncandidate_add", args=[plan_a.pk]), {
        "candidate": employee_a2.pk, "readiness": "ready_now", "rank_order": "1"})
    assert resp.status_code == 302
    c = SuccessionCandidate.objects.get(plan=plan_a, candidate=employee_a2)
    assert plan_a.bench_strength == "moderate"
    # edit
    client_a.post(reverse("hrm:successioncandidate_edit", args=[c.pk]), {
        "candidate": employee_a2.pk, "readiness": "ready_1_2y", "rank_order": "2"})
    c.refresh_from_db()
    assert c.readiness == "ready_1_2y"
    # delete
    client_a.post(reverse("hrm:successioncandidate_delete", args=[c.pk]))
    assert not SuccessionCandidate.objects.filter(pk=c.pk).exists()


# ============================================================ CONFIDENTIALITY (the headline property)
def test_non_admin_forbidden_on_every_talent_view(employee_client, pool_a, star_a, plan_a):
    """A plain employee gets 403 on EVERY 3.38 surface — they must not learn they're on a bench,
    flagged a flight risk, or placed on the 9-box."""
    gets = [("hrm:talentpool_list", []), ("hrm:talentpool_detail", [pool_a.pk]),
            ("hrm:talentpool_create", []), ("hrm:talentpoolmembership_list", []),
            ("hrm:talentpoolmembership_detail", [star_a.pk]), ("hrm:talent_nine_box", []),
            ("hrm:successionplan_list", []), ("hrm:successionplan_detail", [plan_a.pk])]
    for name, args in gets:
        assert employee_client.get(reverse(name, args=args)).status_code == 403, name


def test_anonymous_redirected(client, pool_a):
    resp = client.get(reverse("hrm:talentpool_list"))
    assert resp.status_code == 302 and "/login" in resp.url


def test_multitenant_idor_404(client_a, pool_b, plan_b):
    assert client_a.get(reverse("hrm:talentpool_detail", args=[pool_b.pk])).status_code == 404
    assert client_a.get(reverse("hrm:successionplan_detail", args=[plan_b.pk])).status_code == 404


# ============================================================ 3.38 wiring fix: Internal Mobility deep-link
def test_jobrequisition_posting_type_filter(client_a, tenant_a, designation_a, dept_a):
    """The 'Internal Mobility' sidebar deep-link (?posting_type=internal) must actually filter — before
    the fix, posting_type wasn't in jobrequisition_list's filter tuple so it showed EVERY requisition."""
    from apps.hrm.models import JobRequisition
    internal = JobRequisition.objects.create(
        tenant=tenant_a, title="Internal Team Lead", designation=designation_a, department=dept_a,
        headcount=1, req_type="standard", posting_type="internal")
    external = JobRequisition.objects.create(
        tenant=tenant_a, title="External Engineer", designation=designation_a, department=dept_a,
        headcount=1, req_type="standard", posting_type="external")
    resp = client_a.get(reverse("hrm:jobrequisition_list") + "?posting_type=internal")
    assert resp.status_code == 200
    assert internal.number.encode() in resp.content
    assert external.number.encode() not in resp.content
