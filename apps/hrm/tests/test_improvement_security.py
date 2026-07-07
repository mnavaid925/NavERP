"""Security tests for HRM 3.21 Performance Improvement: CONFIDENTIALITY
(_can_view_pip/_visible_pips_q, _can_view_warning/_visible_warnings_q, and the STRICTEST gate
_can_view_coaching/_visible_coaching_q — the coached employee never sees their own CoachingNote),
the check-in tamper regression (subject self-report, manager-only edit/delete, locked-once-closed),
dropdown scoping on PerformanceImprovementPlanForm/WarningLetterForm/CoachingNoteForm, form-smuggling
guards, and CSRF enforcement. Mirrors test_feedback_security.py conventions."""
import datetime

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _link_user_to_employee(user, employee):
    user.party = employee.party
    user.save(update_fields=["party"])


# ------------------------------------------------------------------ Linked-user client fixtures
@pytest.fixture
def subject_user(db, tenant_a, employee_a):
    """A non-admin tenant_a User linked to employee_a — pip_draft_a's SUBJECT."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="subject@acme.com", username="subject_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, employee_a)
    return user


@pytest.fixture
def subject_client(db, subject_user):
    c = Client()
    c.force_login(subject_user)
    return c


@pytest.fixture
def manager_user(db, tenant_a, employee_a2):
    """A non-admin tenant_a User linked to employee_a2 — pip_draft_a's MANAGER (also warning_draft_a's
    issuer and coaching_note_a's coach)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="manager@acme.com", username="manager_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, employee_a2)
    return user


@pytest.fixture
def manager_client(db, manager_user):
    c = Client()
    c.force_login(manager_user)
    return c


@pytest.fixture
def outsider_user(db, tenant_a, outsider_employee_a):
    """A non-admin, non-subject, non-manager, non-coach tenant_a User (a THIRD employee)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email="outsider@acme.com", username="outsider_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    _link_user_to_employee(user, outsider_employee_a)
    return user


@pytest.fixture
def outsider_client(db, outsider_user):
    c = Client()
    c.force_login(outsider_user)
    return c


# ================================================================ PIP confidentiality (_can_view_pip)
class TestPIPConfidentiality:
    def test_outsider_403_on_detail(self, outsider_client, pip_draft_a):
        resp = outsider_client.get(reverse("hrm:pip_detail", args=[pip_draft_a.pk]))
        assert resp.status_code == 403

    def test_outsider_absent_from_list(self, outsider_client, pip_draft_a):
        resp = outsider_client.get(reverse("hrm:pip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk not in pks

    def test_subject_can_view_detail(self, subject_client, pip_draft_a):
        resp = subject_client.get(reverse("hrm:pip_detail", args=[pip_draft_a.pk]))
        assert resp.status_code == 200

    def test_subject_sees_own_pip_in_list(self, subject_client, pip_draft_a):
        resp = subject_client.get(reverse("hrm:pip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_manager_can_view_detail(self, manager_client, pip_draft_a):
        resp = manager_client.get(reverse("hrm:pip_detail", args=[pip_draft_a.pk]))
        assert resp.status_code == 200

    def test_manager_sees_own_pip_in_list(self, manager_client, pip_draft_a):
        resp = manager_client.get(reverse("hrm:pip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pip_draft_a.pk in pks

    def test_admin_can_view_any_pip(self, client_a, pip_draft_a):
        resp = client_a.get(reverse("hrm:pip_detail", args=[pip_draft_a.pk]))
        assert resp.status_code == 200

    def test_pip_edit_blocked_for_subject(self, subject_client, pip_draft_a):
        """_can_edit_pip: the subject is NEVER an editor, even though they can view it."""
        resp = subject_client.get(reverse("hrm:pip_edit", args=[pip_draft_a.pk]))
        assert resp.status_code == 302

    def test_pip_edit_post_by_subject_does_not_mutate(self, subject_client, pip_draft_a, employee_a, employee_a2):
        original_issue = pip_draft_a.performance_issue
        subject_client.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "tampered", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.performance_issue == original_issue

    def test_pip_edit_allowed_for_manager_while_draft(self, manager_client, pip_draft_a, employee_a, employee_a2):
        resp = manager_client.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "Manager-updated issue.", "expected_standards": "x",
            "improvement_goals": "x", "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
        })
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.performance_issue == "Manager-updated issue."

    def test_pip_edit_locked_for_manager_once_not_draft(self, manager_client, pip_active_a):
        """_can_edit_pip also gates on status=='draft' — the manager is locked out once active."""
        resp = manager_client.get(reverse("hrm:pip_edit", args=[pip_active_a.pk]))
        assert resp.status_code == 302

    def test_outsider_cannot_log_checkin(self, outsider_client, pip_active_a):
        resp = outsider_client.get(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]))
        assert resp.status_code == 403

    def test_outsider_403_on_checkin_detail(self, outsider_client, pipcheckin_a):
        resp = outsider_client.get(reverse("hrm:pipcheckin_detail", args=[pipcheckin_a.pk]))
        assert resp.status_code == 403


# ================================================================ WarningLetter confidentiality
class TestWarningLetterConfidentiality:
    def test_outsider_403_on_detail(self, outsider_client, warning_draft_a):
        resp = outsider_client.get(reverse("hrm:warningletter_detail", args=[warning_draft_a.pk]))
        assert resp.status_code == 403

    def test_outsider_absent_from_list(self, outsider_client, warning_draft_a):
        resp = outsider_client.get(reverse("hrm:warningletter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk not in pks

    def test_recipient_can_view_detail(self, subject_client, warning_draft_a):
        """subject_client is linked to employee_a — warning_draft_a's issued_to (recipient)."""
        resp = subject_client.get(reverse("hrm:warningletter_detail", args=[warning_draft_a.pk]))
        assert resp.status_code == 200

    def test_recipient_sees_own_warning_in_list(self, subject_client, warning_draft_a):
        resp = subject_client.get(reverse("hrm:warningletter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert warning_draft_a.pk in pks

    def test_issuer_can_view_detail(self, manager_client, warning_draft_a):
        """manager_client is linked to employee_a2 — warning_draft_a's issued_by (issuer)."""
        resp = manager_client.get(reverse("hrm:warningletter_detail", args=[warning_draft_a.pk]))
        assert resp.status_code == 200

    def test_admin_can_view_any_warning(self, client_a, warning_draft_a):
        resp = client_a.get(reverse("hrm:warningletter_detail", args=[warning_draft_a.pk]))
        assert resp.status_code == 200

    def test_warningletter_edit_blocked_for_recipient(self, subject_client, warning_draft_a):
        """_can_edit_warning: the recipient is NEVER an editor."""
        resp = subject_client.get(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]))
        assert resp.status_code == 302

    def test_warningletter_edit_post_by_recipient_does_not_mutate(
        self, subject_client, warning_draft_a, employee_a, employee_a2
    ):
        original_description = warning_draft_a.description
        subject_client.post(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "verbal",
            "category": "attendance", "incident_date": "2026-06-01", "description": "tampered",
            "policy_reference": "", "related_pip": "", "expiry_date": "",
        })
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.description == original_description

    def test_warningletter_edit_allowed_for_issuer_while_draft(
        self, manager_client, warning_draft_a, employee_a, employee_a2
    ):
        resp = manager_client.post(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "verbal",
            "category": "attendance", "incident_date": "2026-06-01",
            "description": "Issuer-updated description.", "policy_reference": "", "related_pip": "",
            "expiry_date": "",
        })
        assert resp.status_code == 302
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.description == "Issuer-updated description."

    # ----- prior_warnings on detail scoped to the viewer (never the full history)
    def test_prior_warnings_scoped_to_recipient_viewer(self, tenant_a, employee_a, employee_a2, subject_client):
        """subject_client (the recipient of BOTH warnings) sees the prior warning."""
        from apps.hrm.models import WarningLetter
        earlier = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 3, 1), description="Earlier incident", status="issued",
        )
        later = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Later incident", status="issued",
        )
        resp = subject_client.get(reverse("hrm:warningletter_detail", args=[later.pk]))
        pks = [w.pk for w in resp.context["prior_warnings"]]
        assert earlier.pk in pks

    def test_prior_warnings_hidden_from_outsider_even_via_admin_created_row(
        self, tenant_a, employee_a, employee_a2, outsider_employee_a, outsider_client
    ):
        """An outsider isn't the recipient/issuer of either warning, so _can_view_warning already
        403s them on the LATER letter — sanity-check the gate holds (prior_warnings is moot once the
        detail itself is unreachable)."""
        from apps.hrm.models import WarningLetter
        WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 3, 1), description="Earlier incident", status="issued",
        )
        later = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Later incident", status="issued",
        )
        resp = outsider_client.get(reverse("hrm:warningletter_detail", args=[later.pk]))
        assert resp.status_code == 403

    def test_prior_warnings_scoped_when_viewer_is_only_issuer_of_later_not_earlier(
        self, tenant_a, employee_a, employee_a2, outsider_employee_a
    ):
        """A 3rd employee issues an EARLIER warning to employee_a; employee_a2 issues a LATER one.
        employee_a2 (viewing the later letter) is not party to the earlier one (different issuer),
        so `_visible_warnings_q` must exclude it from `prior_warnings` even though employee_a (the
        shared recipient) links both."""
        from apps.hrm.models import WarningLetter
        from django.test import Client
        from apps.accounts.models import User
        earlier = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=outsider_employee_a,
            incident_date=datetime.date(2026, 3, 1), description="Earlier, different issuer",
            status="issued",
        )
        later = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Later incident", status="issued",
        )
        viewer = User.objects.create_user(
            email="issuer_later@acme.com", username="issuer_later_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False)
        _link_user_to_employee(viewer, employee_a2)
        c = Client()
        c.force_login(viewer)
        resp = c.get(reverse("hrm:warningletter_detail", args=[later.pk]))
        assert resp.status_code == 200
        pks = [w.pk for w in resp.context["prior_warnings"]]
        assert earlier.pk not in pks

    def test_admin_sees_full_prior_warnings_history(self, client_a, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import WarningLetter
        earlier = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 3, 1), description="Earlier incident", status="issued",
        )
        later = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Later incident", status="issued",
        )
        resp = client_a.get(reverse("hrm:warningletter_detail", args=[later.pk]))
        pks = [w.pk for w in resp.context["prior_warnings"]]
        assert earlier.pk in pks


# ================================================================ CoachingNote (STRICTEST) confidentiality
class TestCoachingNoteConfidentiality:
    def test_coached_employee_sees_zero_notes_on_list(self, subject_client, coaching_note_a):
        """subject_client is linked to employee_a — coaching_note_a's COACHED `employee` — and must
        see ZERO of their own coaching notes."""
        resp = subject_client.get(reverse("hrm:coachingnote_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk not in pks
        assert pks == []

    def test_coached_employee_403_on_detail(self, subject_client, coaching_note_a):
        resp = subject_client.get(reverse("hrm:coachingnote_detail", args=[coaching_note_a.pk]))
        assert resp.status_code == 403

    def test_coached_employee_403_on_edit(self, subject_client, coaching_note_a):
        resp = subject_client.get(reverse("hrm:coachingnote_edit", args=[coaching_note_a.pk]))
        assert resp.status_code == 302

    def test_coach_can_view_own_authored_note(self, manager_client, coaching_note_a):
        """manager_client is linked to employee_a2 — coaching_note_a's COACH (author)."""
        resp = manager_client.get(reverse("hrm:coachingnote_detail", args=[coaching_note_a.pk]))
        assert resp.status_code == 200

    def test_coach_sees_own_authored_note_in_list(self, manager_client, coaching_note_a):
        resp = manager_client.get(reverse("hrm:coachingnote_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks

    def test_admin_can_view_any_note(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_detail", args=[coaching_note_a.pk]))
        assert resp.status_code == 200

    def test_admin_list_shows_all_notes(self, client_a, coaching_note_a):
        resp = client_a.get(reverse("hrm:coachingnote_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert coaching_note_a.pk in pks

    def test_outsider_403_on_detail(self, outsider_client, coaching_note_a):
        resp = outsider_client.get(reverse("hrm:coachingnote_detail", args=[coaching_note_a.pk]))
        assert resp.status_code == 403

    # ----- coach is server-set (POST a different coach id -> ignored)
    def test_create_ignores_smuggled_coach_id_uses_request_user(
        self, tenant_a, manager_user, employee_a2, employee_a
    ):
        from apps.hrm.models import CoachingNote
        c = Client()
        c.force_login(manager_user)
        resp = c.post(reverse("hrm:coachingnote_create"), {
            "employee": employee_a.pk, "related_pip": "", "note_date": "2026-07-10",
            "category": "other", "content": "Coach id smuggle attempt",
            "coach": employee_a.pk,  # attempted smuggle: coach == the coached employee
        })
        assert resp.status_code == 302
        note = CoachingNote.objects.filter(
            tenant=tenant_a, employee=employee_a, content="Coach id smuggle attempt").first()
        assert note is not None
        assert note.coach_id == employee_a2.pk  # manager_user's own linked profile, not the smuggled id


# ================================================================ Check-in tamper regression
class TestPIPCheckInTamperRegression:
    def test_subject_can_self_report_checkin(self, subject_client, pip_active_a):
        """The PIP subject CAN pipcheckin_create (self-report)."""
        from apps.hrm.models import PIPCheckIn
        resp = subject_client.post(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]), {
            "checkin_date": "2026-07-20", "progress_rating": "on_track",
            "progress_notes": "Self-reported progress.",
        })
        assert resp.status_code == 302
        assert PIPCheckIn.objects.filter(
            pip=pip_active_a, progress_notes="Self-reported progress.").exists()

    def test_subject_cannot_edit_manager_checkin(self, subject_client, pipcheckin_a):
        """The subject CANNOT edit a manager-authored check-in — redirect-with-error, row unchanged."""
        original_rating = pipcheckin_a.progress_rating
        resp = subject_client.post(reverse("hrm:pipcheckin_edit", args=[pipcheckin_a.pk]), {
            "checkin_date": pipcheckin_a.checkin_date.isoformat(), "progress_rating": "off_track",
            "progress_notes": "Tampered by subject.",
        })
        assert resp.status_code == 302
        pipcheckin_a.refresh_from_db()
        assert pipcheckin_a.progress_rating == original_rating

    def test_subject_cannot_delete_manager_checkin(self, subject_client, pipcheckin_a):
        from apps.hrm.models import PIPCheckIn
        resp = subject_client.post(reverse("hrm:pipcheckin_delete", args=[pipcheckin_a.pk]))
        assert resp.status_code == 302
        assert PIPCheckIn.objects.filter(pk=pipcheckin_a.pk).exists()

    def test_manager_can_edit_own_checkin(self, manager_client, pipcheckin_a):
        resp = manager_client.post(reverse("hrm:pipcheckin_edit", args=[pipcheckin_a.pk]), {
            "checkin_date": pipcheckin_a.checkin_date.isoformat(), "progress_rating": "at_risk",
            "progress_notes": "Manager update.",
        })
        assert resp.status_code == 302
        pipcheckin_a.refresh_from_db()
        assert pipcheckin_a.progress_rating == "at_risk"

    def test_outsider_cannot_edit_checkin(self, outsider_client, pipcheckin_a):
        original_rating = pipcheckin_a.progress_rating
        resp = outsider_client.post(reverse("hrm:pipcheckin_edit", args=[pipcheckin_a.pk]), {
            "checkin_date": pipcheckin_a.checkin_date.isoformat(), "progress_rating": "off_track",
            "progress_notes": "Outsider tamper.",
        })
        assert resp.status_code == 302
        pipcheckin_a.refresh_from_db()
        assert pipcheckin_a.progress_rating == original_rating

    # ----- No check-in create/edit/delete once the plan is closed
    def test_no_checkin_create_once_plan_closed(self, client_a, pip_active_a):
        pip_active_a.status = "closed"
        pip_active_a.outcome = "successful"
        pip_active_a.save(update_fields=["status", "outcome"])
        resp = client_a.get(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]))
        assert resp.status_code == 302

    def test_no_checkin_edit_once_plan_closed_even_for_admin(self, client_a, pip_active_a, pipcheckin_a):
        pip_active_a.status = "closed"
        pip_active_a.outcome = "successful"
        pip_active_a.save(update_fields=["status", "outcome"])
        original_rating = pipcheckin_a.progress_rating
        resp = client_a.post(reverse("hrm:pipcheckin_edit", args=[pipcheckin_a.pk]), {
            "checkin_date": pipcheckin_a.checkin_date.isoformat(), "progress_rating": "off_track",
            "progress_notes": "Post-close tamper.",
        })
        assert resp.status_code == 302
        pipcheckin_a.refresh_from_db()
        assert pipcheckin_a.progress_rating == original_rating

    def test_no_checkin_delete_once_plan_closed_even_for_admin(self, client_a, pip_active_a, pipcheckin_a):
        from apps.hrm.models import PIPCheckIn
        pip_active_a.status = "closed"
        pip_active_a.outcome = "successful"
        pip_active_a.save(update_fields=["status", "outcome"])
        resp = client_a.post(reverse("hrm:pipcheckin_delete", args=[pipcheckin_a.pk]))
        assert resp.status_code == 302
        assert PIPCheckIn.objects.filter(pk=pipcheckin_a.pk).exists()


# ================================================================ Dropdown scoping (form __init__)
class TestPerformanceImprovementPlanFormDropdownScoping:
    def test_excludes_review_non_admin_viewer_cannot_see(
        self, tenant_a, employee_a, employee_a2, review_cycle_a, outsider_employee_a
    ):
        """PerformanceImprovementPlanForm(tenant=t, viewer_profile=p).fields['triggering_review']
        excludes a review neither subject nor reviewer of `p`."""
        from apps.hrm.forms import PerformanceImprovementPlanForm
        from apps.hrm.models import PerformanceReview
        unrelated_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=outsider_employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        form = PerformanceImprovementPlanForm(tenant=tenant_a, viewer_profile=employee_a, viewer_is_admin=False)
        pks = list(form.fields["triggering_review"].queryset.values_list("pk", flat=True))
        assert unrelated_review.pk not in pks

    def test_includes_review_viewer_is_subject_of(self, tenant_a, employee_a, employee_a2, review_cycle_a):
        from apps.hrm.forms import PerformanceImprovementPlanForm
        from apps.hrm.models import PerformanceReview
        own_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        form = PerformanceImprovementPlanForm(tenant=tenant_a, viewer_profile=employee_a, viewer_is_admin=False)
        pks = list(form.fields["triggering_review"].queryset.values_list("pk", flat=True))
        assert own_review.pk in pks

    def test_viewer_is_admin_shows_full_set(
        self, tenant_a, employee_a, employee_a2, review_cycle_a, outsider_employee_a
    ):
        from apps.hrm.forms import PerformanceImprovementPlanForm
        from apps.hrm.models import PerformanceReview
        unrelated_review = PerformanceReview.objects.create(
            tenant=tenant_a, cycle=review_cycle_a, subject=outsider_employee_a, reviewer=employee_a2,
            review_type="manager",
        )
        form = PerformanceImprovementPlanForm(tenant=tenant_a, viewer_profile=None, viewer_is_admin=True)
        pks = list(form.fields["triggering_review"].queryset.values_list("pk", flat=True))
        assert unrelated_review.pk in pks


class TestWarningLetterFormDropdownScoping:
    def test_excludes_pip_non_admin_viewer_cannot_see(
        self, tenant_a, employee_a, employee_a2, outsider_employee_a
    ):
        from apps.hrm.forms import WarningLetterForm
        from apps.hrm.models import PerformanceImprovementPlan
        unrelated_pip = PerformanceImprovementPlan.objects.create(
            tenant=tenant_a, subject=outsider_employee_a, manager=employee_a2, status="draft",
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        form = WarningLetterForm(tenant=tenant_a, viewer_profile=employee_a, viewer_is_admin=False)
        pks = list(form.fields["related_pip"].queryset.values_list("pk", flat=True))
        assert unrelated_pip.pk not in pks

    def test_includes_pip_viewer_is_subject_of(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.forms import WarningLetterForm
        from apps.hrm.models import PerformanceImprovementPlan
        own_pip = PerformanceImprovementPlan.objects.create(
            tenant=tenant_a, subject=employee_a, manager=employee_a2, status="draft",
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        form = WarningLetterForm(tenant=tenant_a, viewer_profile=employee_a, viewer_is_admin=False)
        pks = list(form.fields["related_pip"].queryset.values_list("pk", flat=True))
        assert own_pip.pk in pks

    def test_viewer_is_admin_shows_full_set(self, tenant_a, employee_a, employee_a2, outsider_employee_a):
        from apps.hrm.forms import WarningLetterForm
        from apps.hrm.models import PerformanceImprovementPlan
        unrelated_pip = PerformanceImprovementPlan.objects.create(
            tenant=tenant_a, subject=outsider_employee_a, manager=employee_a2, status="draft",
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        form = WarningLetterForm(tenant=tenant_a, viewer_profile=None, viewer_is_admin=True)
        pks = list(form.fields["related_pip"].queryset.values_list("pk", flat=True))
        assert unrelated_pip.pk in pks


class TestCoachingNoteFormDropdownScoping:
    def test_excludes_pip_non_admin_viewer_cannot_see(
        self, tenant_a, employee_a, employee_a2, outsider_employee_a
    ):
        from apps.hrm.forms import CoachingNoteForm
        from apps.hrm.models import PerformanceImprovementPlan
        unrelated_pip = PerformanceImprovementPlan.objects.create(
            tenant=tenant_a, subject=outsider_employee_a, manager=employee_a2, status="draft",
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        form = CoachingNoteForm(tenant=tenant_a, viewer_profile=employee_a, viewer_is_admin=False)
        pks = list(form.fields["related_pip"].queryset.values_list("pk", flat=True))
        assert unrelated_pip.pk not in pks

    def test_includes_pip_viewer_is_manager_of(self, tenant_a, employee_a, employee_a2):
        """CoachingNoteForm's viewer is the coach — scoping mirrors WarningLetterForm's
        subject-or-manager rule against the viewer's own PIP rows."""
        from apps.hrm.forms import CoachingNoteForm
        from apps.hrm.models import PerformanceImprovementPlan
        own_pip = PerformanceImprovementPlan.objects.create(
            tenant=tenant_a, subject=employee_a, manager=employee_a2, status="draft",
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        form = CoachingNoteForm(tenant=tenant_a, viewer_profile=employee_a2, viewer_is_admin=False)
        pks = list(form.fields["related_pip"].queryset.values_list("pk", flat=True))
        assert own_pip.pk in pks

    def test_viewer_is_admin_shows_full_set(self, tenant_a, employee_a, employee_a2, outsider_employee_a):
        from apps.hrm.forms import CoachingNoteForm
        from apps.hrm.models import PerformanceImprovementPlan
        unrelated_pip = PerformanceImprovementPlan.objects.create(
            tenant=tenant_a, subject=outsider_employee_a, manager=employee_a2, status="draft",
            performance_issue="x", expected_standards="x", improvement_goals="x",
            measurement_criteria="x", start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
        )
        form = CoachingNoteForm(tenant=tenant_a, viewer_profile=None, viewer_is_admin=True)
        pks = list(form.fields["related_pip"].queryset.values_list("pk", flat=True))
        assert unrelated_pip.pk in pks


# ================================================================ Form-smuggling guards
class TestFormFieldExclusions:
    def test_pipform_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import PerformanceImprovementPlanForm
        excluded = {"status", "outcome", "outcome_date", "outcome_notes", "number",
                    "extended_end_date", "acknowledged_at", "acknowledged_by",
                    "hr_approved_at", "hr_approved_by"}
        assert excluded.isdisjoint(set(PerformanceImprovementPlanForm.Meta.fields))

    def test_pip_edit_post_with_status_does_not_write_it(self, client_a, pip_draft_a, employee_a, employee_a2):
        assert pip_draft_a.status == "draft"
        resp = client_a.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "x", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29", "status": "active",
        })
        assert resp.status_code == 302
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "draft"

    def test_pip_edit_post_with_outcome_does_not_write_it(self, client_a, pip_draft_a, employee_a, employee_a2):
        client_a.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "x", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29", "outcome": "successful",
        })
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.outcome == ""

    def test_pip_edit_post_with_acknowledged_at_does_not_write_it(
        self, client_a, pip_draft_a, employee_a, employee_a2
    ):
        client_a.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "x", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
            "acknowledged_at": "2026-01-01T00:00",
        })
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.acknowledged_at is None

    def test_pip_edit_post_with_hr_approved_at_does_not_write_it(
        self, client_a, pip_draft_a, employee_a, employee_a2
    ):
        client_a.post(reverse("hrm:pip_edit", args=[pip_draft_a.pk]), {
            "subject": employee_a.pk, "manager": employee_a2.pk, "triggering_review": "",
            "performance_issue": "x", "expected_standards": "x", "improvement_goals": "x",
            "support_provided": "", "measurement_criteria": "x",
            "start_date": "2026-07-01", "end_date": "2026-09-29",
            "hr_approved_at": "2026-01-01T00:00",
        })
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.hr_approved_at is None

    def test_warningletterform_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import WarningLetterForm
        excluded = {"status", "number", "acknowledged_at", "acknowledged_by", "employee_response"}
        assert excluded.isdisjoint(set(WarningLetterForm.Meta.fields))

    def test_warningletter_edit_post_with_status_does_not_write_it(
        self, client_a, warning_draft_a, employee_a, employee_a2
    ):
        assert warning_draft_a.status == "draft"
        resp = client_a.post(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "verbal",
            "category": "attendance", "incident_date": "2026-06-01", "description": "x",
            "policy_reference": "", "related_pip": "", "expiry_date": "", "status": "issued",
        })
        assert resp.status_code == 302
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.status == "draft"

    def test_warningletter_edit_post_with_acknowledged_at_does_not_write_it(
        self, client_a, warning_draft_a, employee_a, employee_a2
    ):
        client_a.post(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "verbal",
            "category": "attendance", "incident_date": "2026-06-01", "description": "x",
            "policy_reference": "", "related_pip": "", "expiry_date": "",
            "acknowledged_at": "2026-01-01T00:00",
        })
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.acknowledged_at is None

    def test_warningletter_edit_post_with_employee_response_does_not_write_it(
        self, client_a, warning_draft_a, employee_a, employee_a2
    ):
        """employee_response is captured ONLY via WarningAcknowledgeForm — the general edit form
        must not expose it."""
        client_a.post(reverse("hrm:warningletter_edit", args=[warning_draft_a.pk]), {
            "issued_to": employee_a.pk, "issued_by": employee_a2.pk, "level": "verbal",
            "category": "attendance", "incident_date": "2026-06-01", "description": "x",
            "policy_reference": "", "related_pip": "", "expiry_date": "",
            "employee_response": "smuggled response",
        })
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.employee_response == ""

    def test_coachingnoteform_excludes_coach_status_and_number(self):
        from apps.hrm.forms import CoachingNoteForm
        excluded = {"coach", "status", "number"}
        assert excluded.isdisjoint(set(CoachingNoteForm.Meta.fields))

    def test_coachingnote_edit_post_with_coach_does_not_reassign(
        self, client_a, coaching_note_a, employee_a, employee_a2, outsider_employee_a
    ):
        """CoachingNoteForm has no `coach` field — POSTing a different coach pk via the general edit
        form must NOT reassign it."""
        original_coach_id = coaching_note_a.coach_id
        client_a.post(reverse("hrm:coachingnote_edit", args=[coaching_note_a.pk]), {
            "employee": employee_a.pk, "related_pip": "", "note_date": "2026-07-05",
            "category": "other", "content": "x", "coach": outsider_employee_a.pk,
        })
        coaching_note_a.refresh_from_db()
        assert coaching_note_a.coach_id == original_coach_id


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_pip_delete_enforces_csrf(self, admin_user, pip_draft_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:pip_delete", args=[pip_draft_a.pk]))
        assert resp.status_code == 403

    def test_pip_submit_enforces_csrf(self, admin_user, pip_draft_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:pip_submit", args=[pip_draft_a.pk]))
        assert resp.status_code == 403
        pip_draft_a.refresh_from_db()
        assert pip_draft_a.status == "draft"

    def test_pip_hr_approve_enforces_csrf(self, admin_user, pip_draft_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:pip_hr_approve", args=[pip_draft_a.pk]))
        assert resp.status_code == 403

    def test_pip_acknowledge_enforces_csrf(self, admin_user, employee_a, pip_active_a):
        _link_user_to_employee(admin_user, employee_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:pip_acknowledge", args=[pip_active_a.pk]))
        assert resp.status_code == 403
        pip_active_a.refresh_from_db()
        assert pip_active_a.acknowledged_at is None

    def test_pip_extend_enforces_csrf(self, admin_user, pip_active_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:pip_extend", args=[pip_active_a.pk]), {
            "extended_end_date": "2099-01-01",
        })
        assert resp.status_code == 403

    def test_pipcheckin_delete_enforces_csrf(self, admin_user, pipcheckin_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:pipcheckin_delete", args=[pipcheckin_a.pk]))
        assert resp.status_code == 403

    def test_warningletter_delete_enforces_csrf(self, admin_user, warning_draft_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:warningletter_delete", args=[warning_draft_a.pk]))
        assert resp.status_code == 403

    def test_warningletter_issue_enforces_csrf(self, admin_user, warning_draft_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:warningletter_issue", args=[warning_draft_a.pk]))
        assert resp.status_code == 403
        warning_draft_a.refresh_from_db()
        assert warning_draft_a.status == "draft"

    def test_warningletter_acknowledge_enforces_csrf(self, admin_user, employee_a, warning_issued_a):
        _link_user_to_employee(admin_user, employee_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:warningletter_acknowledge", args=[warning_issued_a.pk]), {
            "employee_response": "x",
        })
        assert resp.status_code == 403
        warning_issued_a.refresh_from_db()
        assert warning_issued_a.status == "issued"

    def test_coachingnote_delete_enforces_csrf(self, admin_user, coaching_note_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:coachingnote_delete", args=[coaching_note_a.pk]))
        assert resp.status_code == 403


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlockedOnFeedbackDrivenActions:
    def test_anon_blocked_on_checkin_create(self, client, pip_active_a):
        resp = client.get(reverse("hrm:pipcheckin_create", args=[pip_active_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_coachingnote_create(self, client):
        resp = client.get(reverse("hrm:coachingnote_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_warningletter_acknowledge(self, client, warning_issued_a):
        resp = client.post(reverse("hrm:warningletter_acknowledge", args=[warning_issued_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_pip_close(self, client, pip_active_a):
        resp = client.get(reverse("hrm:pip_close", args=[pip_active_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
