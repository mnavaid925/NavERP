"""3.41 Employee Engagement & Wellbeing — models, forms, views, authorization, tenant isolation.

Covers the traps this sub-module is prone to:
  * model-layer confidentiality: WellbeingProgram.save() FORCES is_confidential=True for eap_counseling
    (a form default alone would be bypassable via a crafted POST / direct .create),
  * the confidential-program roster is aggregate-only for EVERYONE including admins,
  * WellbeingParticipationForm(can_admin=False) drops points_earned + narrows status (a non-admin can't
    self-award points or self-mark attended),
  * the (tenant, program, employee) unique_together — a duplicate RSVP is a friendly error, never a 500,
  * SurveyActionPlan.completed_at auto-stamp/clear symmetry + is_overdue,
  * _can_manage_action_plan owner-vs-admin-vs-stranger,
  * FlexibleWorkArrangement's _hr_request_* lifecycle + own-vs-admin scoping,
  * cross-tenant IDOR -> 404.
"""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import OrgUnit, Party
from apps.hrm.models import (
    EmployeeProfile, FlexibleWorkArrangement, Survey, SurveyActionPlan, WellbeingParticipation,
    WellbeingProgram)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------- fixtures
@pytest.fixture
def survey_a(db, tenant_a):
    return Survey.objects.create(tenant=tenant_a, title="Pulse", status="closed",
                                 questions=[{"text": "q", "type": "rating"}])


@pytest.fixture
def action_plan_a(db, tenant_a, survey_a, employee_a):
    return SurveyActionPlan.objects.create(
        tenant=tenant_a, survey=survey_a, title="Improve growth", focus_area="Career Growth",
        owner=employee_a, description="Ladders + reviews.",
        target_date=timezone.localdate() + datetime.timedelta(days=30), status="open")


@pytest.fixture
def program_a(db, tenant_a):
    return WellbeingProgram.objects.create(tenant=tenant_a, title="Step Challenge",
                                           program_type="wellness_challenge", status="active",
                                           points_value=100)


@pytest.fixture
def self_service_client(db, member_user, employee_a):
    from django.test import Client
    member_user.party = employee_a.party
    member_user.save(update_fields=["party"])
    c = Client()
    c.force_login(member_user)
    return c


@pytest.fixture
def other_employee_a(db, tenant_a, designation_a):
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Other Person")
    return EmployeeProfile.objects.create(tenant=tenant_a, party=party, designation=designation_a,
                                          employee_type="full_time")


# ---------------------------------------------------------------------------- models
def test_action_plan_number_is_auto_assigned(action_plan_a):
    assert action_plan_a.number.startswith("ACTP-")


def test_action_plan_completed_at_is_auto_stamped_and_cleared(tenant_a, survey_a, employee_a):
    plan = SurveyActionPlan.objects.create(
        tenant=tenant_a, survey=survey_a, title="X", focus_area="Y", owner=employee_a,
        description="Z", target_date=timezone.localdate(), status="open")
    assert plan.completed_at is None
    plan.status = "completed"
    plan.save()
    assert plan.completed_at is not None
    # Reopening clears it symmetrically.
    plan.status = "in_progress"
    plan.save()
    assert plan.completed_at is None


def test_action_plan_is_overdue(tenant_a, survey_a, employee_a):
    past = timezone.localdate() - datetime.timedelta(days=1)
    overdue = SurveyActionPlan.objects.create(
        tenant=tenant_a, survey=survey_a, title="A", focus_area="F", owner=employee_a,
        description="D", target_date=past, status="in_progress")
    assert overdue.is_overdue is True
    # A completed plan past its date is NOT overdue.
    done = SurveyActionPlan.objects.create(
        tenant=tenant_a, survey=survey_a, title="B", focus_area="F", owner=employee_a,
        description="D", target_date=past, status="completed")
    assert done.is_overdue is False


def test_eap_program_is_forced_confidential_by_the_model(tenant_a):
    """The model's save() forces is_confidential=True — a direct create(is_confidential=False) can't win."""
    prog = WellbeingProgram.objects.create(tenant=tenant_a, title="EAP", program_type="eap_counseling",
                                           is_confidential=False)
    assert prog.is_confidential is True


def test_a_non_eap_program_keeps_its_confidential_choice(tenant_a):
    prog = WellbeingProgram.objects.create(tenant=tenant_a, title="Event", program_type="team_event",
                                           is_confidential=False)
    assert prog.is_confidential is False


def test_program_number_prefix(program_a):
    assert program_a.number.startswith("WBP-")


def test_participation_stats_aggregates(tenant_a, program_a, employee_a, other_employee_a):
    WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a, employee=employee_a,
                                          status="completed", points_earned=100)
    WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a, employee=other_employee_a,
                                          status="registered")
    stats = program_a.participation_stats()
    assert stats["completed"] == 1
    assert stats["registered"] == 1
    assert stats["total"] == 2
    assert stats["total_points"] == 100


def test_participation_completed_at_auto_managed(tenant_a, program_a, employee_a):
    p = WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a, employee=employee_a,
                                              status="registered")
    assert p.completed_at is None
    p.status = "completed"
    p.save()
    assert p.completed_at is not None


def test_fwa_number_prefix(tenant_a, employee_a):
    fwa = FlexibleWorkArrangement.objects.create(
        tenant=tenant_a, employee=employee_a, arrangement_type="remote",
        start_date=timezone.localdate(), reason="wfh")
    assert fwa.number.startswith("FWA-")


# ---------------------------------------------------------------------------- forms
def test_participation_form_drops_points_and_narrows_status_for_non_admin():
    from apps.hrm.forms import WellbeingParticipationForm
    non_admin = WellbeingParticipationForm(can_admin=False, tenant=None)
    assert "points_earned" not in non_admin.fields
    assert {c[0] for c in non_admin.fields["status"].choices} == {"registered", "withdrawn"}
    admin = WellbeingParticipationForm(can_admin=True, tenant=None)
    assert "points_earned" in admin.fields
    assert len(admin.fields["status"].choices) == 5


def test_fwa_form_requires_days_for_remote(tenant_a):
    from apps.hrm.forms import FlexibleWorkArrangementForm
    form = FlexibleWorkArrangementForm(
        {"arrangement_type": "remote", "start_date": timezone.localdate().isoformat(), "reason": "x"},
        tenant=tenant_a)
    assert not form.is_valid()
    assert "days_per_week_remote" in form.errors


def test_fwa_form_rejects_days_for_non_remote(tenant_a):
    from apps.hrm.forms import FlexibleWorkArrangementForm
    form = FlexibleWorkArrangementForm(
        {"arrangement_type": "flextime", "start_date": timezone.localdate().isoformat(),
         "days_per_week_remote": 3, "reason": "x"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "days_per_week_remote" in form.errors


# ---------------------------------------------------------------------------- authorization
ADMIN_ONLY_ROUTES = [
    ("hrm:surveyactionplan_create", []),
    ("hrm:wellbeingprogram_create", []),
]


@pytest.mark.parametrize("route,args", ADMIN_ONLY_ROUTES)
def test_admin_can_open_admin_pages(client_a, route, args):
    assert client_a.get(reverse(route, args=args)).status_code == 200


@pytest.mark.parametrize("route,args", ADMIN_ONLY_ROUTES)
def test_a_plain_employee_cannot_open_admin_pages(self_service_client, route, args):
    assert self_service_client.get(reverse(route, args=args)).status_code in (302, 403)


def test_a_plain_employee_can_browse_the_program_catalog(self_service_client, program_a):
    assert self_service_client.get(reverse("hrm:wellbeingprogram_list")).status_code == 200
    assert self_service_client.get(
        reverse("hrm:wellbeingprogram_detail", args=[program_a.pk])).status_code == 200


# ---------------------------------------------------------------------------- confidentiality (the crux)
def test_confidential_program_hides_the_roster_from_an_admin(client_a, tenant_a, employee_a):
    prog = WellbeingProgram.objects.create(tenant=tenant_a, title="EAP", program_type="eap_counseling",
                                           status="active")
    WellbeingParticipation.objects.create(tenant=tenant_a, program=prog, employee=employee_a,
                                          status="registered")
    resp = client_a.get(reverse("hrm:wellbeingprogram_detail", args=[prog.pk]))
    assert resp.status_code == 200
    # Aggregate-only: even an ADMIN gets no per-employee roster queryset.
    assert resp.context["participations"] is None
    assert resp.context["stats"]["total"] == 1


def test_non_confidential_program_shows_the_roster(client_a, tenant_a, program_a, employee_a):
    WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a, employee=employee_a,
                                          status="registered")
    resp = client_a.get(reverse("hrm:wellbeingprogram_detail", args=[program_a.pk]))
    assert resp.context["participations"] is not None
    assert len(resp.context["participations"]) == 1


# ---------------------------------------------------------------------------- participation self-service
def test_an_employee_can_rsvp_to_a_program(self_service_client, tenant_a, program_a, employee_a):
    resp = self_service_client.post(
        reverse("hrm:wellbeingparticipation_add", args=[program_a.pk]),
        {"status": "registered", "notes": "count me in"})
    assert resp.status_code == 302
    assert WellbeingParticipation.objects.filter(tenant=tenant_a, program=program_a,
                                                 employee=employee_a).exists()


def test_a_non_admin_cannot_self_award_points(self_service_client, tenant_a, program_a, employee_a):
    """points_earned is dropped from the form for a non-admin — a crafted POST is ignored, not honoured."""
    self_service_client.post(reverse("hrm:wellbeingparticipation_add", args=[program_a.pk]),
                             {"status": "registered", "points_earned": "999", "notes": ""})
    p = WellbeingParticipation.objects.get(tenant=tenant_a, program=program_a, employee=employee_a)
    assert p.points_earned is None


def test_a_non_admin_cannot_self_mark_attended(self_service_client, tenant_a, program_a, employee_a):
    """status choices are narrowed to registered/withdrawn — 'completed' is rejected by the form."""
    self_service_client.post(reverse("hrm:wellbeingparticipation_add", args=[program_a.pk]),
                             {"status": "completed", "notes": ""})
    assert not WellbeingParticipation.objects.filter(tenant=tenant_a, program=program_a,
                                                     status="completed").exists()


def test_a_duplicate_rsvp_is_a_friendly_error_not_a_500(self_service_client, tenant_a, program_a,
                                                        employee_a):
    WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a, employee=employee_a,
                                          status="registered")
    resp = self_service_client.post(reverse("hrm:wellbeingparticipation_add", args=[program_a.pk]),
                                    {"status": "registered", "notes": ""})
    assert resp.status_code in (200, 302)   # never a 500
    assert WellbeingParticipation.objects.filter(tenant=tenant_a, program=program_a,
                                                 employee=employee_a).count() == 1


def test_cannot_join_a_non_active_program(self_service_client, tenant_a, employee_a):
    draft = WellbeingProgram.objects.create(tenant=tenant_a, title="Draft", program_type="team_event",
                                            status="draft")
    self_service_client.post(reverse("hrm:wellbeingparticipation_add", args=[draft.pk]),
                             {"status": "registered", "notes": ""})
    assert not WellbeingParticipation.objects.filter(tenant=tenant_a, program=draft).exists()


def test_an_admin_can_award_points_when_editing_a_participation(client_a, tenant_a, program_a,
                                                               employee_a):
    p = WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a, employee=employee_a,
                                              status="registered")
    resp = client_a.post(
        reverse("hrm:wellbeingparticipation_edit", args=[program_a.pk, p.pk]),
        {"status": "completed", "points_earned": "100", "notes": ""})
    assert resp.status_code == 302
    p.refresh_from_db()
    assert p.status == "completed" and p.points_earned == 100


def test_an_employee_cannot_edit_another_persons_participation(self_service_client, tenant_a, program_a,
                                                              other_employee_a):
    theirs = WellbeingParticipation.objects.create(tenant=tenant_a, program=program_a,
                                                   employee=other_employee_a, status="registered")
    resp = self_service_client.post(
        reverse("hrm:wellbeingparticipation_edit", args=[program_a.pk, theirs.pk]),
        {"status": "withdrawn", "notes": ""})
    assert resp.status_code == 302          # bounced with an error
    theirs.refresh_from_db()
    assert theirs.status == "registered"    # unchanged


# ---------------------------------------------------------------------------- action-plan ownership
def test_the_owner_can_edit_their_action_plan(self_service_client, action_plan_a):
    resp = self_service_client.get(reverse("hrm:surveyactionplan_edit", args=[action_plan_a.pk]))
    assert resp.status_code == 200


def test_a_stranger_cannot_edit_an_action_plan(member_client, action_plan_a):
    """member_client's user has no employee profile / isn't the owner / isn't an admin -> 403."""
    resp = member_client.get(reverse("hrm:surveyactionplan_edit", args=[action_plan_a.pk]))
    assert resp.status_code == 403


def test_an_admin_can_edit_any_action_plan(client_a, action_plan_a):
    assert client_a.get(reverse("hrm:surveyactionplan_edit", args=[action_plan_a.pk])).status_code == 200


def test_only_an_admin_can_delete_an_action_plan(self_service_client, tenant_a, action_plan_a):
    resp = self_service_client.post(reverse("hrm:surveyactionplan_delete", args=[action_plan_a.pk]))
    assert resp.status_code in (302, 403)
    assert SurveyActionPlan.objects.filter(pk=action_plan_a.pk).exists()


# ---------------------------------------------------------------------------- FWA workflow
def test_fwa_submit_then_approve(client_a, self_service_client, tenant_a, employee_a):
    self_service_client.post(reverse("hrm:flexibleworkarrangement_create"), {
        "arrangement_type": "compressed_week", "start_date": timezone.localdate().isoformat(),
        "reason": "family"})
    fwa = FlexibleWorkArrangement.objects.get(tenant=tenant_a, employee=employee_a)
    self_service_client.post(reverse("hrm:flexibleworkarrangement_submit", args=[fwa.pk]))
    fwa.refresh_from_db()
    assert fwa.status == "pending"
    client_a.post(reverse("hrm:flexibleworkarrangement_approve", args=[fwa.pk]))
    fwa.refresh_from_db()
    assert fwa.status == "approved" and fwa.approver_id is not None


def test_fwa_reject_requires_a_reason(client_a, tenant_a, employee_a):
    fwa = FlexibleWorkArrangement.objects.create(
        tenant=tenant_a, employee=employee_a, arrangement_type="remote", days_per_week_remote=2,
        start_date=timezone.localdate(), reason="x", status="pending")
    client_a.post(reverse("hrm:flexibleworkarrangement_reject", args=[fwa.pk]), {"decision_note": ""})
    fwa.refresh_from_db()
    assert fwa.status == "pending"          # no reason -> not rejected
    client_a.post(reverse("hrm:flexibleworkarrangement_reject", args=[fwa.pk]),
                  {"decision_note": "coverage"})
    fwa.refresh_from_db()
    assert fwa.status == "rejected"


def test_fwa_list_scopes_a_non_admin_to_their_own(self_service_client, tenant_a, employee_a,
                                                  other_employee_a):
    FlexibleWorkArrangement.objects.create(tenant=tenant_a, employee=employee_a,
                                           arrangement_type="flextime", start_date=timezone.localdate(),
                                           reason="mine")
    FlexibleWorkArrangement.objects.create(tenant=tenant_a, employee=other_employee_a,
                                           arrangement_type="flextime", start_date=timezone.localdate(),
                                           reason="theirs")
    resp = self_service_client.get(reverse("hrm:flexibleworkarrangement_list"))
    reasons = {o.reason for o in resp.context["object_list"]}
    assert reasons == {"mine"}


def test_a_plain_employee_cannot_approve_an_fwa(self_service_client, tenant_a, other_employee_a):
    fwa = FlexibleWorkArrangement.objects.create(
        tenant=tenant_a, employee=other_employee_a, arrangement_type="remote", days_per_week_remote=2,
        start_date=timezone.localdate(), reason="x", status="pending")
    resp = self_service_client.post(reverse("hrm:flexibleworkarrangement_approve", args=[fwa.pk]))
    assert resp.status_code in (302, 403)
    fwa.refresh_from_db()
    assert fwa.status == "pending"


# ---------------------------------------------------------------------------- tenant isolation
def test_action_plan_from_another_tenant_is_404(client_a, tenant_b):
    survey_b = Survey.objects.create(tenant=tenant_b, title="B", status="closed",
                                     questions=[{"text": "q", "type": "rating"}])
    party_b = Party.objects.create(tenant=tenant_b, kind="person", name="B Person")
    emp_b = EmployeeProfile.objects.create(tenant=tenant_b, party=party_b, employee_type="full_time")
    foreign = SurveyActionPlan.objects.create(
        tenant=tenant_b, survey=survey_b, title="F", focus_area="F", owner=emp_b, description="D",
        target_date=timezone.localdate())
    assert client_a.get(reverse("hrm:surveyactionplan_detail", args=[foreign.pk])).status_code == 404


def test_program_from_another_tenant_is_404(client_a, tenant_b):
    foreign = WellbeingProgram.objects.create(tenant=tenant_b, title="F", program_type="team_event")
    assert client_a.get(reverse("hrm:wellbeingprogram_detail", args=[foreign.pk])).status_code == 404
    assert client_a.post(reverse("hrm:wellbeingprogram_delete", args=[foreign.pk])).status_code == 404


def test_fwa_from_another_tenant_is_404(client_a, tenant_b):
    party_b = Party.objects.create(tenant=tenant_b, kind="person", name="B Person")
    emp_b = EmployeeProfile.objects.create(tenant=tenant_b, party=party_b, employee_type="full_time")
    foreign = FlexibleWorkArrangement.objects.create(
        tenant=tenant_b, employee=emp_b, arrangement_type="remote", days_per_week_remote=2,
        start_date=timezone.localdate(), reason="x")
    assert client_a.get(
        reverse("hrm:flexibleworkarrangement_detail", args=[foreign.pk])).status_code == 404


def test_program_list_never_leaks_another_tenant(client_a, tenant_a, tenant_b):
    WellbeingProgram.objects.create(tenant=tenant_b, title="Foreign", program_type="team_event")
    WellbeingProgram.objects.create(tenant=tenant_a, title="Mine", program_type="team_event")
    resp = client_a.get(reverse("hrm:wellbeingprogram_list"))
    assert {p.title for p in resp.context["object_list"]} == {"Mine"}
