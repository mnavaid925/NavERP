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
def test_list_annotations_match_unannotated_properties(client_a, tenant_a, plan_a, pool_a, star_a,
                                                       employee_a, employee_a2):
    """The list views ANNOTATE the counts that bench_strength / active_member_count read (to avoid a
    per-row N+1). Guard that the annotated result equals the plain (query-based) property — two filtered
    Count()s over one relation can silently mis-count without distinct=True."""
    from apps.hrm.models import SuccessionCandidate, SuccessionPlan, TalentPool
    SuccessionCandidate.objects.create(tenant=tenant_a, plan=plan_a, candidate=employee_a,
                                       readiness="ready_now", rank_order=1)
    SuccessionCandidate.objects.create(tenant=tenant_a, plan=plan_a, candidate=employee_a2,
                                       readiness="ready_1_2y", rank_order=2)
    # Unannotated (fresh instance) → query-based property.
    plain = SuccessionPlan.objects.get(pk=plan_a.pk)
    assert plain.candidate_count == 2 and plain.ready_now_count == 1
    assert plain.bench_strength == "moderate"

    # Annotated, exactly as successionplan_list builds it.
    resp = client_a.get(reverse("hrm:successionplan_list"))
    assert resp.status_code == 200
    annotated = resp.context["object_list"][0]
    assert annotated.candidate_count == 2 and annotated.ready_now_count == 1
    assert annotated.bench_strength == "moderate"
    assert b"Moderate" in resp.content

    # Same for the pool's active-member annotation.
    resp = client_a.get(reverse("hrm:talentpool_list"))
    pool = resp.context["object_list"][0]
    assert pool.active_member_count == TalentPool.objects.get(pk=pool_a.pk).active_member_count == 1


def test_successioncandidate_add_duplicate_is_rejected(client_a, tenant_a, plan_a, employee_a):
    """unique_together(tenant, plan, candidate) on the INLINE add: adding the same employee twice must
    be rejected cleanly (no 500, no duplicate row) — the form's clean() now guards the add path too."""
    from apps.hrm.models import SuccessionCandidate
    SuccessionCandidate.objects.create(tenant=tenant_a, plan=plan_a, candidate=employee_a,
                                       readiness="ready_now", rank_order=1)
    resp = client_a.post(reverse("hrm:successioncandidate_add", args=[plan_a.pk]), {
        "candidate": employee_a.pk, "readiness": "ready_1_2y", "rank_order": "2"})
    assert resp.status_code == 302  # redirects back to the plan with an error message
    assert SuccessionCandidate.objects.filter(plan=plan_a, candidate=employee_a).count() == 1


def test_successioncandidate_add_duplicate_leaves_transaction_usable(client_a, tenant_a, plan_a,
                                                                     employee_a):
    """Regression (code-review Critical): the duplicate-successor IntegrityError must be caught inside a
    SAVEPOINT (transaction.atomic()). Without it the exception poisons the surrounding transaction and
    the very next query blows up with TransactionManagementError (surfacing as SessionInterrupted)."""
    from apps.hrm.models import SuccessionCandidate
    SuccessionCandidate.objects.create(tenant=tenant_a, plan=plan_a, candidate=employee_a,
                                       readiness="ready_now", rank_order=1)
    resp = client_a.post(reverse("hrm:successioncandidate_add", args=[plan_a.pk]), {
        "candidate": employee_a.pk, "readiness": "ready_1_2y", "rank_order": "2"})
    assert resp.status_code == 302
    # The connection must still be usable — this is what regressed before the savepoint fix.
    assert SuccessionCandidate.objects.filter(plan=plan_a).count() == 1
    assert client_a.get(reverse("hrm:successionplan_list")).status_code == 200


def test_annotated_lists_are_ordered_for_pagination(client_a, tenant_a, designation_a):
    """Regression (code-review Important): annotate() adds a GROUP BY that DROPS Meta.ordering, so the
    paginator would silently duplicate/skip rows. Both annotated lists must come back ordered."""
    from apps.hrm.models import SuccessionPlan, TalentPool
    for i in range(20):
        TalentPool.objects.create(tenant=tenant_a, name=f"Pool {i:02d}", pool_type="hipo")
        SuccessionPlan.objects.create(tenant=tenant_a, critical_role=designation_a, status="active")

    for url_name in ("hrm:talentpool_list", "hrm:successionplan_list"):
        resp = client_a.get(reverse(url_name))
        assert resp.status_code == 200
        assert resp.context["page_obj"].object_list.ordered, f"{url_name} paginates an UNORDERED qs"
        # Page 1 and page 2 must not overlap (the symptom an unordered qs produces).
        p1 = {o.pk for o in resp.context["object_list"]}
        p2 = {o.pk for o in client_a.get(reverse(url_name) + "?page=2").context["object_list"]}
        assert p1 and p2 and not (p1 & p2), f"{url_name} repeated a row across pages"


def _query_count(client, url):
    """Queries fired by one GET of ``url`` (must not grow with row count)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


def test_successionplan_list_query_count_is_flat(client_a, tenant_a, designation_a,
                                                 employee_a, employee_a2):
    """bench_strength renders on EVERY row and reads 2 counts — the annotation must keep the query
    count FLAT as plans grow (it was 2 COUNTs per row before the fix)."""
    from apps.hrm.models import SuccessionCandidate, SuccessionPlan
    url = reverse("hrm:successionplan_list")

    def _plan_with_bench():
        p = SuccessionPlan.objects.create(tenant=tenant_a, critical_role=designation_a, status="active")
        SuccessionCandidate.objects.create(tenant=tenant_a, plan=p, candidate=employee_a,
                                           readiness="ready_now", rank_order=1)
        SuccessionCandidate.objects.create(tenant=tenant_a, plan=p, candidate=employee_a2,
                                           readiness="ready_1_2y", rank_order=2)

    _plan_with_bench()
    baseline = _query_count(client_a, url)
    for _ in range(4):
        _plan_with_bench()
    assert _query_count(client_a, url) == baseline, "successionplan_list regressed to an N+1"


def test_talentpool_list_query_count_is_flat(client_a, tenant_a, employee_a, employee_a2):
    """active_member_count renders per row — the annotation must keep the count flat."""
    from apps.hrm.models import TalentPool, TalentPoolMembership
    url = reverse("hrm:talentpool_list")

    def _pool(i):
        p = TalentPool.objects.create(tenant=tenant_a, name=f"Pool {i}", pool_type="hipo")
        TalentPoolMembership.objects.create(tenant=tenant_a, pool=p, employee=employee_a, status="active")
        TalentPoolMembership.objects.create(tenant=tenant_a, pool=p, employee=employee_a2, status="active")

    _pool(0)
    baseline = _query_count(client_a, url)
    for i in range(1, 5):
        _pool(i)
    assert _query_count(client_a, url) == baseline, "talentpool_list regressed to an N+1"


def test_membership_list_query_count_is_flat(client_a, tenant_a, employee_a,
                                             performance_review_a, review_rating_a):
    """The 9-box axis falls back to review.effective_rating -> overall_rating -> review.ratings when
    calibrated_rating is null. The review__ratings prefetch must keep the count flat."""
    from apps.hrm.models import TalentPool, TalentPoolMembership
    url = reverse("hrm:talentpoolmembership_list")
    assert performance_review_a.calibrated_rating is None  # forces the ratings fallback path

    def _membership(i):
        p = TalentPool.objects.create(tenant=tenant_a, name=f"MP {i}", pool_type="hipo")
        TalentPoolMembership.objects.create(tenant=tenant_a, pool=p, employee=employee_a,
                                            review=performance_review_a)

    _membership(0)
    baseline = _query_count(client_a, url)
    for i in range(1, 5):
        _membership(i)
    assert _query_count(client_a, url) == baseline, "talentpoolmembership_list regressed to an N+1"


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


# ============================================================ QA smoke: full URL sweep (gap 1)
@pytest.fixture
def candidate_a(db, tenant_a, plan_a, employee_a2):
    """A ranked successor on plan_a's bench (used to GET successioncandidate_edit)."""
    from apps.hrm.models import SuccessionCandidate
    return SuccessionCandidate.objects.create(
        tenant=tenant_a, plan=plan_a, candidate=employee_a2, readiness="ready_now", rank_order=1)


def test_full_url_sweep_get_200(client_a, pool_a, star_a, plan_a, candidate_a):
    """Every 3.38 list/create/detail/edit GET renders 200 for a tenant admin (create/delete-only
    endpoints like successioncandidate_add/successioncandidate_delete/*_delete are POST-only and are
    exercised via POST in the CRUD-cycle tests below, not here)."""
    gets = [
        ("hrm:talentpool_list", []),
        ("hrm:talentpool_create", []),
        ("hrm:talentpool_detail", [pool_a.pk]),
        ("hrm:talentpool_edit", [pool_a.pk]),
        ("hrm:talentpoolmembership_list", []),
        ("hrm:talentpoolmembership_create", []),
        ("hrm:talentpoolmembership_detail", [star_a.pk]),
        ("hrm:talentpoolmembership_edit", [star_a.pk]),
        ("hrm:talent_nine_box", []),
        ("hrm:successionplan_list", []),
        ("hrm:successionplan_create", []),
        ("hrm:successionplan_detail", [plan_a.pk]),
        ("hrm:successionplan_edit", [plan_a.pk]),
        ("hrm:successioncandidate_edit", [candidate_a.pk]),
    ]
    for name, args in gets:
        resp = client_a.get(reverse(name, args=args))
        assert resp.status_code == 200, f"{name}{args} -> {resp.status_code}"


def test_filtered_list_renders(client_a, tenant_a, pool_a, star_a):
    """One filtered list (?q= + a choice filter) — must still 200, not throw on the combined filter."""
    resp = client_a.get(reverse("hrm:talentpoolmembership_list") + "?q=a&status=active&flight_risk=low")
    assert resp.status_code == 200
    assert star_a.employee.party.name.encode() in resp.content


# ============================================================ QA smoke: full CRUD cycles (gap 2)
def test_talentpool_full_crud_cycle(client_a, tenant_a, employee_a):
    """create -> edit -> delete via POST, each a 302 redirect, with the DB reflecting every step."""
    from apps.hrm.models import TalentPool
    resp = client_a.post(reverse("hrm:talentpool_create"), {
        "name": "Rising Stars", "pool_type": "hipo", "description": "",
        "owner": employee_a.pk, "is_active": "on"})
    assert resp.status_code == 302
    obj = TalentPool.objects.get(tenant=tenant_a, name="Rising Stars")

    resp = client_a.post(reverse("hrm:talentpool_edit", args=[obj.pk]), {
        "name": "Rising Stars Updated", "pool_type": "leadership", "description": "Updated",
        "owner": employee_a.pk, "is_active": "on"})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.name == "Rising Stars Updated" and obj.pool_type == "leadership"

    resp = client_a.post(reverse("hrm:talentpool_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not TalentPool.objects.filter(pk=obj.pk).exists()


def test_talentpoolmembership_full_crud_cycle(client_a, tenant_a, pool_a, employee_a2):
    """create -> edit -> delete via POST for a membership NOT already covered by the star_a fixture."""
    from apps.hrm.models import TalentPoolMembership
    resp = client_a.post(reverse("hrm:talentpoolmembership_create"), {
        "pool": pool_a.pk, "employee": employee_a2.pk, "joined_on": TODAY.isoformat(),
        "status": "active", "flight_risk": "low"})
    assert resp.status_code == 302
    obj = TalentPoolMembership.objects.get(tenant=tenant_a, pool=pool_a, employee=employee_a2)

    resp = client_a.post(reverse("hrm:talentpoolmembership_edit", args=[obj.pk]), {
        "pool": pool_a.pk, "employee": employee_a2.pk, "joined_on": TODAY.isoformat(),
        "status": "active", "flight_risk": "high",
        "performance_rating": "3.50", "potential_rating": "3.60"})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.flight_risk == "high" and obj.performance_rating == Decimal("3.50")

    resp = client_a.post(reverse("hrm:talentpoolmembership_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not TalentPoolMembership.objects.filter(pk=obj.pk).exists()


def test_successionplan_full_crud_cycle(client_a, tenant_a, designation_a, employee_a):
    """create -> edit -> delete via POST for a plan NOT already covered by the plan_a fixture."""
    from apps.hrm.models import SuccessionPlan
    resp = client_a.post(reverse("hrm:successionplan_create"), {
        "critical_role": designation_a.pk, "incumbent": employee_a.pk,
        "vacancy_risk": "medium", "status": "draft", "review_date": TODAY.isoformat(), "notes": ""})
    assert resp.status_code == 302
    obj = SuccessionPlan.objects.filter(tenant=tenant_a).order_by("-created_at").first()
    assert obj is not None and obj.number.startswith("SPL-")

    resp = client_a.post(reverse("hrm:successionplan_edit", args=[obj.pk]), {
        "critical_role": designation_a.pk, "incumbent": employee_a.pk,
        "vacancy_risk": "high", "status": "active", "review_date": TODAY.isoformat(),
        "notes": "Updated"})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.vacancy_risk == "high" and obj.status == "active" and obj.notes == "Updated"

    resp = client_a.post(reverse("hrm:successionplan_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not SuccessionPlan.objects.filter(pk=obj.pk).exists()


# ============================================================ QA smoke: comment-leak scan (gap 3)
def test_no_template_comment_leak_across_talent_pages(client_a, pool_a, star_a, plan_a):
    """``{#`` / ``{% comment`` must never reach rendered HTML on any 3.38 list/detail page, incl. the
    9-box grid."""
    urls = [
        reverse("hrm:talentpool_list"),
        reverse("hrm:talentpool_detail", args=[pool_a.pk]),
        reverse("hrm:talentpoolmembership_list"),
        reverse("hrm:talentpoolmembership_detail", args=[star_a.pk]),
        reverse("hrm:successionplan_list"),
        reverse("hrm:successionplan_detail", args=[plan_a.pk]),
        reverse("hrm:talent_nine_box"),
    ]
    for url in urls:
        resp = client_a.get(url)
        assert resp.status_code == 200, url
        content = resp.content.decode()
        assert "{#" not in content, f"comment-leak marker in {url}"
        assert "{% comment" not in content, f"comment-leak marker in {url}"


# ============================================================ QA smoke: nine-box ?pool= filter (gap 4)
@pytest.fixture
def pool_a2(db, tenant_a):
    from apps.hrm.models import TalentPool
    return TalentPool.objects.create(tenant=tenant_a, name="Leadership Pipeline 2", pool_type="leadership")


def test_nine_box_pool_filter_scopes_grid_and_unrated_is_unplaced(client_a, tenant_a, pool_a, pool_a2,
                                                                   star_a, employee_a2):
    """``?pool=<id>`` scopes the grid to that pool only; a same-pool member with no rating lands in the
    "unplaced" section, while a rated member of a DIFFERENT pool is excluded entirely from the response."""
    unrated_in_pool = _member(tenant_a, pool_a, employee_a2)                       # no ratings -> unplaced
    rated_in_other_pool = _member(tenant_a, pool_a2, employee_a2, Decimal("4.5"), Decimal("4.6"))

    resp = client_a.get(reverse("hrm:talent_nine_box") + f"?pool={pool_a.pk}")
    assert resp.status_code == 200
    content = resp.content.decode()

    star_href = reverse("hrm:talentpoolmembership_detail", args=[star_a.pk])
    unrated_href = reverse("hrm:talentpoolmembership_detail", args=[unrated_in_pool.pk])
    other_href = reverse("hrm:talentpoolmembership_detail", args=[rated_in_other_pool.pk])

    assert star_href in content            # placed (Star), scoped to pool_a
    assert unrated_href in content         # unplaced, scoped to pool_a
    assert other_href not in content       # different pool -> excluded entirely by the filter
    assert resp.context["placed_count"] == 1 and resp.context["total"] == 2

    # Sanity: without the filter, the OTHER pool's member IS included.
    resp_all = client_a.get(reverse("hrm:talent_nine_box"))
    assert other_href in resp_all.content.decode()
