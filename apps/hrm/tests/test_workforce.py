"""3.40 Workforce Planning — models, forms, views, tenant isolation and authorization.

Covers the traps this sub-module is prone to:
  * the annotation-aware ``WorkforcePlan`` totals (the list annotation and the detail's per-instance
    aggregate fallback must agree),
  * the ``unique_together`` guards (a duplicate must redisplay the form, never 500 on IntegrityError),
  * the admin-only boundary on plan/line/scenario/gap/analytics — these carry RESTRUCTURING and
    REDUCTION headcount, which a plain employee must never see,
  * own-vs-admin self-service on ``EmployeeSkill``,
  * cross-tenant IDOR -> 404.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import OrgUnit, Party
from apps.hrm.models import (
    EmployeeProfile, EmployeeSkill, WorkforcePlan, WorkforcePlanLine, WorkforceScenario)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------- fixtures
@pytest.fixture
def plan_a(db, tenant_a, dept_a):
    today = timezone.localdate()
    return WorkforcePlan.objects.create(
        tenant=tenant_a, name="FY Plan", org_unit=dept_a, plan_type="annual",
        period_start=today, period_end=today + datetime.timedelta(days=365), status="active")


@pytest.fixture
def self_service_client(db, member_user, employee_a):
    """A non-admin login bound to employee_a's Party — this is what _current_employee_profile()
    resolves through (User.party -> Party.employee_profile)."""
    from django.test import Client
    member_user.party = employee_a.party
    member_user.save(update_fields=["party"])
    c = Client()
    c.force_login(member_user)
    return c


@pytest.fixture
def other_employee_a(db, tenant_a, dept_a, designation_a):
    """A SECOND employee in tenant_a — the one the self-service user must NOT be able to reach."""
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Other Person")
    return EmployeeProfile.objects.create(
        tenant=tenant_a, party=party, designation=designation_a, employee_type="full_time")


# ---------------------------------------------------------------------------- models
def test_plan_number_is_auto_assigned(plan_a):
    assert plan_a.number.startswith("WFP-")


def test_line_gap_and_budget_impact_are_computed(tenant_a, plan_a, dept_a):
    line = WorkforcePlanLine.objects.create(
        tenant=tenant_a, plan=plan_a, org_unit=dept_a, current_headcount=10, planned_headcount=14,
        hiring_type="new_growth", avg_annual_cost=Decimal("50000.00"))
    assert line.headcount_gap == 4
    assert line.budget_impact == Decimal("200000.00")


def test_line_budget_impact_is_none_without_a_cost(tenant_a, plan_a, dept_a):
    """None, not 0 — an unpriced line must not be silently treated as free."""
    line = WorkforcePlanLine.objects.create(
        tenant=tenant_a, plan=plan_a, org_unit=dept_a, current_headcount=5, planned_headcount=3)
    assert line.headcount_gap == -2
    assert line.budget_impact is None


def test_a_reduction_line_yields_a_negative_gap_and_a_saving(tenant_a, plan_a, dept_a):
    line = WorkforcePlanLine.objects.create(
        tenant=tenant_a, plan=plan_a, org_unit=dept_a, current_headcount=10, planned_headcount=7,
        hiring_type="reduction", avg_annual_cost=Decimal("60000.00"))
    assert line.headcount_gap == -3
    assert line.budget_impact == Decimal("-180000.00")


def test_plan_totals_roll_up_from_the_lines(tenant_a, plan_a, dept_a):
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=10, planned_headcount=14,
                                     avg_annual_cost=Decimal("50000.00"))
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=4, planned_headcount=2,
                                     avg_annual_cost=Decimal("40000.00"))
    plan_a.refresh_from_db()
    assert plan_a.total_current_headcount == 14
    assert plan_a.total_planned_headcount == 16
    assert plan_a.total_gap == 2
    # 4 * 50000 + (-2) * 40000 — the reduction line nets off against the growth line.
    assert plan_a.total_budget_impact == Decimal("120000.00")


def test_an_unpriced_line_is_excluded_from_the_budget_impact(tenant_a, plan_a, dept_a):
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=1, planned_headcount=3,
                                     avg_annual_cost=Decimal("10000.00"))
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=1, planned_headcount=9)  # no cost
    assert plan_a.total_budget_impact == Decimal("20000.00")
    assert plan_a.total_gap == 10       # ...but it still counts toward the headcount gap


def test_plan_totals_are_zero_without_lines(plan_a):
    assert plan_a.total_current_headcount == 0
    assert plan_a.total_planned_headcount == 0
    assert plan_a.total_gap == 0
    assert plan_a.total_budget_impact == Decimal("0")


def test_scenario_resulting_headcount_applies_a_signed_delta(tenant_a, plan_a, dept_a):
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=10, planned_headcount=20)
    s = WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="Freeze",
                                         scenario_type="freeze", headcount_delta=-6)
    assert s.number.startswith("WFS-")
    assert s.resulting_headcount == 14


# ---------------------------------------------------------------------------- authorization
ADMIN_ONLY_ROUTES = [
    "hrm:workforceplan_list",
    "hrm:workforceplan_create",
    "hrm:workforcescenario_list",
    "hrm:workforcescenario_create",
    "hrm:workforce_gap_analysis",
    "hrm:workforce_analytics",
]


@pytest.mark.parametrize("route", ADMIN_ONLY_ROUTES)
def test_an_admin_can_open_the_planning_pages(client_a, route):
    assert client_a.get(reverse(route)).status_code == 200


@pytest.mark.parametrize("route", ADMIN_ONLY_ROUTES)
def test_a_plain_employee_cannot_reach_the_planning_pages(self_service_client, route):
    """Headcount plans carry RESTRUCTURING and REDUCTION lines — a non-admin must never see them."""
    resp = self_service_client.get(reverse(route))
    assert resp.status_code in (302, 403)


def test_a_plain_employee_cannot_open_a_plan_detail(self_service_client, plan_a):
    resp = self_service_client.get(reverse("hrm:workforceplan_detail", args=[plan_a.pk]))
    assert resp.status_code in (302, 403)


def test_a_plain_employee_cannot_delete_a_plan(self_service_client, plan_a):
    resp = self_service_client.post(reverse("hrm:workforceplan_delete", args=[plan_a.pk]))
    assert resp.status_code in (302, 403)
    assert WorkforcePlan.objects.filter(pk=plan_a.pk).exists()


# ---------------------------------------------------------------------------- plan CRUD
def test_an_admin_creates_a_plan(client_a, tenant_a, dept_a):
    today = timezone.localdate()
    resp = client_a.post(reverse("hrm:workforceplan_create"), {
        "name": "Growth Plan", "org_unit": dept_a.pk, "plan_type": "annual",
        "period_start": today.isoformat(),
        "period_end": (today + datetime.timedelta(days=180)).isoformat(),
        "status": "draft", "notes": ""})
    assert resp.status_code == 302
    assert WorkforcePlan.objects.filter(tenant=tenant_a, name="Growth Plan").exists()


def test_a_plan_period_cannot_end_before_it_starts(client_a, tenant_a, dept_a):
    today = timezone.localdate()
    resp = client_a.post(reverse("hrm:workforceplan_create"), {
        "name": "Backwards", "org_unit": dept_a.pk, "plan_type": "annual",
        "period_start": today.isoformat(),
        "period_end": (today - datetime.timedelta(days=5)).isoformat(),
        "status": "draft"})
    assert resp.status_code == 200          # redisplayed with an error, not saved
    assert not WorkforcePlan.objects.filter(tenant=tenant_a, name="Backwards").exists()


def test_a_duplicate_plan_name_is_rejected_not_a_500(client_a, tenant_a, plan_a, dept_a):
    """unique_together(tenant, name). Django skips validate_unique because `tenant` is form-excluded,
    so the form's clean() has to catch it — otherwise this is an IntegrityError -> 500."""
    today = timezone.localdate()
    resp = client_a.post(reverse("hrm:workforceplan_create"), {
        "name": plan_a.name, "org_unit": dept_a.pk, "plan_type": "annual",
        "period_start": today.isoformat(),
        "period_end": (today + datetime.timedelta(days=30)).isoformat(),
        "status": "draft"})
    assert resp.status_code == 200
    assert b"already exists" in resp.content
    assert WorkforcePlan.objects.filter(tenant=tenant_a, name=plan_a.name).count() == 1


def test_an_admin_adds_a_line_to_a_plan(client_a, tenant_a, plan_a, dept_a):
    resp = client_a.post(reverse("hrm:workforceplanline_add", args=[plan_a.pk]), {
        "org_unit": dept_a.pk, "current_headcount": 8, "planned_headcount": 12,
        "hiring_type": "new_growth", "avg_annual_cost": "70000.00", "notes": ""})
    assert resp.status_code == 302
    line = WorkforcePlanLine.objects.get(tenant=tenant_a, plan=plan_a)
    assert line.headcount_gap == 4


def test_a_line_cannot_carry_a_negative_cost(client_a, tenant_a, plan_a, dept_a):
    client_a.post(reverse("hrm:workforceplanline_add", args=[plan_a.pk]), {
        "org_unit": dept_a.pk, "current_headcount": 1, "planned_headcount": 2,
        "hiring_type": "new_growth", "avg_annual_cost": "-500.00"})
    assert not WorkforcePlanLine.objects.filter(tenant=tenant_a, plan=plan_a).exists()


def test_the_plan_detail_totals_match_the_list_annotation(client_a, tenant_a, plan_a, dept_a):
    """The list ANNOTATES the totals; the detail falls back to a per-instance aggregate. They must
    agree — if they don't, the annotation-aware property is wired up wrong."""
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=10, planned_headcount=15)

    detail = client_a.get(reverse("hrm:workforceplan_detail", args=[plan_a.pk]))
    assert detail.context["obj"].total_current_headcount == 10
    assert detail.context["obj"].total_planned_headcount == 15

    listing = client_a.get(reverse("hrm:workforceplan_list"))
    row = [p for p in listing.context["object_list"] if p.pk == plan_a.pk][0]
    assert row.total_current_headcount == 10
    assert row.total_planned_headcount == 15
    assert row.total_gap == 5


def test_the_plan_list_status_filter_works(client_a, tenant_a, plan_a, dept_a):
    today = timezone.localdate()
    WorkforcePlan.objects.create(tenant=tenant_a, name="A Draft", org_unit=dept_a,
                                 period_start=today, period_end=today + datetime.timedelta(days=30),
                                 status="draft")
    resp = client_a.get(reverse("hrm:workforceplan_list"), {"status": "draft"})
    assert {p.name for p in resp.context["object_list"]} == {"A Draft"}


def test_deleting_a_plan_cascades_to_its_lines_and_scenarios(client_a, tenant_a, plan_a, dept_a):
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=1, planned_headcount=2)
    WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="S1")
    client_a.post(reverse("hrm:workforceplan_delete", args=[plan_a.pk]))
    assert not WorkforcePlan.objects.filter(pk=plan_a.pk).exists()
    assert not WorkforcePlanLine.objects.filter(tenant=tenant_a).exists()
    assert not WorkforceScenario.objects.filter(tenant=tenant_a).exists()


# ---------------------------------------------------------------------------- scenarios
def test_an_admin_creates_a_signed_reduction_scenario(client_a, tenant_a, plan_a):
    resp = client_a.post(reverse("hrm:workforcescenario_create"), {
        "plan": plan_a.pk, "name": "Restructure", "scenario_type": "restructuring",
        "headcount_delta": -4, "cost_delta": "-250000.00", "status": "draft"})
    assert resp.status_code == 302
    s = WorkforceScenario.objects.get(tenant=tenant_a, name="Restructure")
    assert s.headcount_delta == -4
    assert s.cost_delta == Decimal("-250000.00")


def test_a_duplicate_scenario_name_on_the_same_plan_is_rejected(client_a, tenant_a, plan_a):
    WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="Freeze",
                                     scenario_type="freeze")
    resp = client_a.post(reverse("hrm:workforcescenario_create"), {
        "plan": plan_a.pk, "name": "Freeze", "scenario_type": "freeze", "headcount_delta": -2,
        "cost_delta": "0", "status": "draft"})
    assert resp.status_code == 200
    assert WorkforceScenario.objects.filter(tenant=tenant_a, plan=plan_a, name="Freeze").count() == 1


def test_the_same_scenario_name_is_allowed_on_a_different_plan(client_a, tenant_a, plan_a, dept_a):
    """unique_together is (tenant, plan, name) — not (tenant, name)."""
    today = timezone.localdate()
    other = WorkforcePlan.objects.create(tenant=tenant_a, name="Second Plan", org_unit=dept_a,
                                         period_start=today,
                                         period_end=today + datetime.timedelta(days=30))
    WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="Freeze")
    resp = client_a.post(reverse("hrm:workforcescenario_create"), {
        "plan": other.pk, "name": "Freeze", "scenario_type": "freeze", "headcount_delta": 0,
        "cost_delta": "0", "status": "draft"})
    assert resp.status_code == 302
    assert WorkforceScenario.objects.filter(tenant=tenant_a, name="Freeze").count() == 2


def test_only_one_scenario_per_plan_can_be_the_baseline(client_a, tenant_a, plan_a):
    """Creating a new baseline demotes the plan's existing baseline (one-baseline-per-plan)."""
    a = WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="A", is_baseline=True)
    resp = client_a.post(reverse("hrm:workforcescenario_create"), {
        "plan": plan_a.pk, "name": "B", "scenario_type": "growth", "headcount_delta": 0,
        "cost_delta": "0", "status": "draft", "is_baseline": "on"})
    assert resp.status_code == 302
    a.refresh_from_db()
    assert a.is_baseline is False
    assert WorkforceScenario.objects.get(tenant=tenant_a, name="B").is_baseline is True
    assert WorkforceScenario.objects.filter(tenant=tenant_a, plan=plan_a, is_baseline=True).count() == 1


def test_editing_a_scenario_to_baseline_demotes_the_others(client_a, tenant_a, plan_a):
    a = WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="A", is_baseline=True)
    b = WorkforceScenario.objects.create(tenant=tenant_a, plan=plan_a, name="B", is_baseline=False)
    resp = client_a.post(reverse("hrm:workforcescenario_edit", args=[b.pk]), {
        "plan": plan_a.pk, "name": "B", "scenario_type": "growth", "headcount_delta": 0,
        "cost_delta": "0", "status": "draft", "is_baseline": "on"})
    assert resp.status_code == 302
    a.refresh_from_db(); b.refresh_from_db()
    assert b.is_baseline is True
    assert a.is_baseline is False


def test_baseline_normalization_is_scoped_to_the_one_plan(client_a, tenant_a, plan_a, dept_a):
    """A baseline on plan X must NOT clear a baseline on plan Y."""
    today = timezone.localdate()
    other_plan = WorkforcePlan.objects.create(tenant=tenant_a, name="Other", org_unit=dept_a,
                                              period_start=today,
                                              period_end=today + datetime.timedelta(days=30))
    other_baseline = WorkforceScenario.objects.create(tenant=tenant_a, plan=other_plan,
                                                      name="Other Baseline", is_baseline=True)
    client_a.post(reverse("hrm:workforcescenario_create"), {
        "plan": plan_a.pk, "name": "New Baseline", "scenario_type": "growth", "headcount_delta": 0,
        "cost_delta": "0", "status": "draft", "is_baseline": "on"})
    other_baseline.refresh_from_db()
    assert other_baseline.is_baseline is True       # untouched — different plan


def test_new_scenario_link_preselects_the_plan(client_a, tenant_a, plan_a):
    """?plan=<id> on the create page seeds the plan dropdown (the plan-detail 'New Scenario' link)."""
    resp = client_a.get(reverse("hrm:workforcescenario_create"), {"plan": plan_a.pk})
    assert resp.status_code == 200
    assert resp.context["form"].initial.get("plan") == plan_a.pk


# ---------------------------------------------------------------------------- gap analysis
def test_gap_analysis_aggregates_by_department(client_a, tenant_a, plan_a, dept_a):
    other = OrgUnit.objects.create(tenant=tenant_a, name="Support", kind="department")
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=10, planned_headcount=14)
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=other,
                                     current_headcount=6, planned_headcount=4)
    resp = client_a.get(reverse("hrm:workforce_gap_analysis"))
    assert resp.status_code == 200
    rows = {d["name"]: d for d in resp.context["departments"]}
    assert rows[dept_a.name]["gap"] == 4
    assert rows["Support"]["gap"] == -2
    assert resp.context["total_current"] == 16
    assert resp.context["total_planned"] == 18
    assert resp.context["total_gap"] == 2


def test_gap_analysis_does_not_merge_two_org_units_with_the_same_name(client_a, tenant_a, plan_a,
                                                                     dept_a):
    """core.OrgUnit doesn't enforce unique names — two distinct "Support" departments must stay two
    separate report rows, not collapse into one (which would mask a reduction)."""
    support_eng = OrgUnit.objects.create(tenant=tenant_a, name="Support", kind="department")
    support_sales = OrgUnit.objects.create(tenant=tenant_a, name="Support", kind="department")
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=support_eng,
                                     current_headcount=10, planned_headcount=15)   # +5 growth
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=support_sales,
                                     current_headcount=20, planned_headcount=18)   # -2 reduction
    resp = client_a.get(reverse("hrm:workforce_gap_analysis"))
    support_rows = [d for d in resp.context["departments"] if d["name"] == "Support"]
    assert len(support_rows) == 2
    assert sorted(d["gap"] for d in support_rows) == [-2, 5]


def test_gap_analysis_ignores_draft_and_archived_plans(client_a, tenant_a, dept_a):
    today = timezone.localdate()
    draft = WorkforcePlan.objects.create(
        tenant=tenant_a, name="Draft Plan", org_unit=dept_a, period_start=today,
        period_end=today + datetime.timedelta(days=90), status="draft")
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=draft, org_unit=dept_a,
                                     current_headcount=100, planned_headcount=200)
    resp = client_a.get(reverse("hrm:workforce_gap_analysis"))
    assert resp.context["total_current"] == 0
    assert resp.context["departments"] == []


def test_gap_analysis_can_be_scoped_to_one_plan(client_a, tenant_a, plan_a, dept_a):
    today = timezone.localdate()
    other = WorkforcePlan.objects.create(tenant=tenant_a, name="Other Active", org_unit=dept_a,
                                         period_start=today,
                                         period_end=today + datetime.timedelta(days=30),
                                         status="active")
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=10, planned_headcount=12)
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=other, org_unit=dept_a,
                                     current_headcount=50, planned_headcount=60)
    resp = client_a.get(reverse("hrm:workforce_gap_analysis"), {"plan": plan_a.pk})
    assert resp.context["total_current"] == 10
    assert resp.context["total_gap"] == 2


def test_gap_analysis_survives_a_bogus_plan_param(client_a):
    """A hand-edited ?plan=abc must not 500 — the digit guard skips the filter."""
    assert client_a.get(reverse("hrm:workforce_gap_analysis"),
                        {"plan": "abc"}).status_code == 200


# ---------------------------------------------------------------------------- analytics
def test_analytics_reports_skill_coverage(client_a, tenant_a, employee_a):
    EmployeeSkill.objects.create(tenant=tenant_a, employee=employee_a, skill_name="Python",
                                 is_critical_skill=True, is_certified=True)
    resp = client_a.get(reverse("hrm:workforce_analytics"))
    assert resp.status_code == 200
    assert resp.context["skill_count"] == 1
    assert resp.context["critical_skill_count"] == 1
    assert resp.context["certified_skill_count"] == 1
    assert resp.context["employees_with_skills"] == 1
    assert resp.context["skill_coverage_percent"] == 100.0


def test_analytics_does_not_divide_by_zero_without_employees(client_a, tenant_a):
    resp = client_a.get(reverse("hrm:workforce_analytics"))
    assert resp.status_code == 200
    assert resp.context["headcount"] == 0
    assert resp.context["skill_coverage_percent"] == 0


def test_analytics_labels_each_hiring_mix_row(client_a, tenant_a, plan_a, dept_a):
    """A Django template can't index a dict by a variable key, so the view must resolve the label."""
    WorkforcePlanLine.objects.create(tenant=tenant_a, plan=plan_a, org_unit=dept_a,
                                     current_headcount=1, planned_headcount=2,
                                     hiring_type="attrition_backfill")
    resp = client_a.get(reverse("hrm:workforce_analytics"))
    assert resp.context["hiring_mix"][0]["label"] == "Attrition Backfill"


# ---------------------------------------------------------------------------- EmployeeSkill (self-service)
def test_an_employee_adds_a_skill_to_their_own_profile(self_service_client, tenant_a, employee_a):
    resp = self_service_client.post(reverse("hrm:employeeskill_create"), {
        "skill_name": "Django", "skill_category": "technical", "proficiency_level": "advanced",
        "years_experience": 5, "certification_name": "", "notes": ""})
    assert resp.status_code == 302
    skill = EmployeeSkill.objects.get(tenant=tenant_a, skill_name="Django")
    assert skill.employee == employee_a


def test_a_duplicate_skill_is_rejected_not_a_500(self_service_client, tenant_a, employee_a):
    """unique_together(tenant, employee, skill_name). The view seeds the unsaved instance with
    tenant+employee so the form's clean() guard fires; the savepoint is the backstop."""
    EmployeeSkill.objects.create(tenant=tenant_a, employee=employee_a, skill_name="Django")
    resp = self_service_client.post(reverse("hrm:employeeskill_create"), {
        "skill_name": "Django", "skill_category": "technical", "proficiency_level": "beginner"})
    assert resp.status_code in (200, 302)   # redisplayed or bounced — never a 500
    assert EmployeeSkill.objects.filter(tenant=tenant_a, employee=employee_a,
                                        skill_name="Django").count() == 1


def test_an_employee_only_sees_their_own_skills(self_service_client, tenant_a, employee_a,
                                                other_employee_a):
    EmployeeSkill.objects.create(tenant=tenant_a, employee=employee_a, skill_name="Mine")
    EmployeeSkill.objects.create(tenant=tenant_a, employee=other_employee_a, skill_name="Theirs")
    resp = self_service_client.get(reverse("hrm:employeeskill_list"))
    assert {s.skill_name for s in resp.context["object_list"]} == {"Mine"}
    assert resp.context["is_admin"] is False


def test_an_employee_cannot_open_someone_elses_skill(self_service_client, tenant_a, other_employee_a):
    """The module-wide self-service contract: a non-owner is refused with 403 (PermissionDenied)."""
    theirs = EmployeeSkill.objects.create(tenant=tenant_a, employee=other_employee_a,
                                          skill_name="Theirs")
    assert self_service_client.get(
        reverse("hrm:employeeskill_detail", args=[theirs.pk])).status_code == 403


def test_an_employee_cannot_delete_someone_elses_skill(self_service_client, tenant_a,
                                                       other_employee_a):
    """Delete bounces a non-owner back to the list with an error and leaves the row intact — it must
    NEVER remove another employee's skill."""
    theirs = EmployeeSkill.objects.create(tenant=tenant_a, employee=other_employee_a,
                                          skill_name="Theirs")
    resp = self_service_client.post(reverse("hrm:employeeskill_delete", args=[theirs.pk]))
    assert resp.status_code == 302
    assert EmployeeSkill.objects.filter(pk=theirs.pk).exists()


def test_an_admin_sees_the_whole_skills_inventory(client_a, tenant_a, employee_a, other_employee_a):
    EmployeeSkill.objects.create(tenant=tenant_a, employee=employee_a, skill_name="Python")
    EmployeeSkill.objects.create(tenant=tenant_a, employee=other_employee_a, skill_name="Go")
    resp = client_a.get(reverse("hrm:employeeskill_list"))
    assert resp.context["is_admin"] is True
    assert len(resp.context["object_list"]) == 2


def test_an_admin_adds_a_skill_to_a_chosen_employee(client_a, tenant_a, other_employee_a):
    resp = client_a.post(reverse("hrm:employeeskill_create"), {
        "employee_pk": other_employee_a.pk, "skill_name": "Kubernetes",
        "skill_category": "technical", "proficiency_level": "expert"})
    assert resp.status_code == 302
    assert EmployeeSkill.objects.get(tenant=tenant_a, skill_name="Kubernetes").employee == other_employee_a


def test_the_critical_skill_filter_uses_a_capitalized_bool(client_a, tenant_a, employee_a):
    """crud_list maps only "True"/"False" to a real bool — a lowercase value is silently skipped."""
    EmployeeSkill.objects.create(tenant=tenant_a, employee=employee_a, skill_name="Critical",
                                 is_critical_skill=True)
    EmployeeSkill.objects.create(tenant=tenant_a, employee=employee_a, skill_name="Ordinary",
                                 is_critical_skill=False)
    resp = client_a.get(reverse("hrm:employeeskill_list"), {"is_critical_skill": "True"})
    assert {s.skill_name for s in resp.context["object_list"]} == {"Critical"}


# ---------------------------------------------------------------------------- tenant isolation
def test_a_plan_from_another_tenant_is_a_404(client_a, tenant_b):
    today = timezone.localdate()
    foreign = WorkforcePlan.objects.create(
        tenant=tenant_b, name="Foreign Plan", period_start=today,
        period_end=today + datetime.timedelta(days=30), status="active")
    assert client_a.get(
        reverse("hrm:workforceplan_detail", args=[foreign.pk])).status_code == 404
    assert client_a.post(
        reverse("hrm:workforceplan_delete", args=[foreign.pk])).status_code == 404
    assert WorkforcePlan.objects.filter(pk=foreign.pk).exists()


def test_a_scenario_from_another_tenant_is_a_404(client_a, tenant_b):
    today = timezone.localdate()
    foreign_plan = WorkforcePlan.objects.create(
        tenant=tenant_b, name="Foreign Plan 2", period_start=today,
        period_end=today + datetime.timedelta(days=30))
    foreign = WorkforceScenario.objects.create(tenant=tenant_b, plan=foreign_plan, name="Foreign")
    assert client_a.get(
        reverse("hrm:workforcescenario_detail", args=[foreign.pk])).status_code == 404


def test_a_plan_line_from_another_tenant_is_a_404(client_a, tenant_b, dept_b):
    today = timezone.localdate()
    foreign_plan = WorkforcePlan.objects.create(
        tenant=tenant_b, name="Foreign Plan 3", period_start=today,
        period_end=today + datetime.timedelta(days=30))
    foreign_line = WorkforcePlanLine.objects.create(
        tenant=tenant_b, plan=foreign_plan, org_unit=dept_b, current_headcount=1, planned_headcount=2)
    assert client_a.get(
        reverse("hrm:workforceplanline_edit", args=[foreign_line.pk])).status_code == 404
    assert client_a.post(
        reverse("hrm:workforceplanline_delete", args=[foreign_line.pk])).status_code == 404
    assert WorkforcePlanLine.objects.filter(pk=foreign_line.pk).exists()


def test_the_plan_list_never_leaks_another_tenants_rows(client_a, tenant_a, tenant_b):
    today = timezone.localdate()
    WorkforcePlan.objects.create(tenant=tenant_b, name="Foreign", period_start=today,
                                 period_end=today + datetime.timedelta(days=30))
    WorkforcePlan.objects.create(tenant=tenant_a, name="Mine", period_start=today,
                                 period_end=today + datetime.timedelta(days=30))
    resp = client_a.get(reverse("hrm:workforceplan_list"))
    assert {p.name for p in resp.context["object_list"]} == {"Mine"}


def test_gap_analysis_never_counts_another_tenants_lines(client_a, tenant_a, tenant_b, dept_b):
    today = timezone.localdate()
    foreign_plan = WorkforcePlan.objects.create(
        tenant=tenant_b, name="Foreign Active", period_start=today,
        period_end=today + datetime.timedelta(days=30), status="active")
    WorkforcePlanLine.objects.create(tenant=tenant_b, plan=foreign_plan, org_unit=dept_b,
                                     current_headcount=99, planned_headcount=999)
    resp = client_a.get(reverse("hrm:workforce_gap_analysis"))
    assert resp.context["total_current"] == 0
    assert resp.context["departments"] == []


def test_a_non_admin_cannot_mass_assign_employee_via_employee_pk(self_service_client, tenant_a,
                                                                 employee_a, other_employee_a):
    """Mass-assignment guard: employeeskill_create only honours employee_pk when _is_admin — a
    non-admin POSTing employee_pk=<someone else> is silently forced onto their OWN profile."""
    resp = self_service_client.post(reverse("hrm:employeeskill_create"), {
        "employee_pk": str(other_employee_a.pk),
        "skill_name": "Underhanded Skill",
        "skill_category": "technical",
        "proficiency_level": "expert",
        "is_critical_skill": "on",
    })
    assert resp.status_code == 302
    skill = EmployeeSkill.objects.get(tenant=tenant_a, skill_name="Underhanded Skill")
    assert skill.employee_id == employee_a.pk           # bound to the attacker, not the victim
    assert skill.employee_id != other_employee_a.pk
