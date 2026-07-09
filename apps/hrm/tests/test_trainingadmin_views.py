"""Tests for HRM 3.24 Training Administration views: ``TrainingNomination`` CRUD + the
approve/reject/waitlist/cancel/withdraw workflow (mirrors the ``LeaveRequest`` approve/reject
manager-gating shape); ``TrainingAttendance`` CRUD + the feedback/certificate-linked delete guard;
``TrainingFeedback`` nested-create (attendee-or-admin only) + ownership-gated edit/delete;
``TrainingCertificate`` CRUD (tenant-admin-only mint/edit/delete/revoke — pin the security fix),
the two "issue from ..." convenience routes (completed-only + certification-only guards, and the
duplicate-issuance guard), and revoke; plus the computed ``training_budget`` view. client_a is the
tenant admin (mirrors test_training_views.py / test_lms_views.py conventions)."""
import datetime

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h=0, mi=0):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


def _nomination_post_data(session, employee, **overrides):
    data = {
        "session": session.pk, "employee": employee.pk, "nominated_by": "",
        "nomination_type": "self", "justification": "", "priority": "normal",
    }
    data.update(overrides)
    return data


def _attendance_post_data(session, employee, **overrides):
    data = {
        "session": session.pk, "employee": employee.pk, "nomination": "",
        "attendance_status": "registered", "completion_status": "not_completed",
        "check_in_at": "", "check_out_at": "", "notes": "",
    }
    data.update(overrides)
    return data


def _feedback_post_data(**overrides):
    data = {
        "overall_rating": "5", "content_rating": "4", "trainer_rating": "5",
        "would_recommend": "on", "comments": "", "is_anonymous": "",
    }
    data.update(overrides)
    return data


def _certificate_post_data(employee, course, **overrides):
    data = {
        "employee": employee.pk, "course": course.pk, "source_attendance": "",
        "source_progress": "", "title": "", "issued_on": "2026-07-10",
    }
    data.update(overrides)
    return data


def _client_for(party, tenant, *, email, username, is_admin=False):
    """Build a logged-in Client for a User linked to the given Party (mirrors the manager_lms /
    carolN_acme convention used across the HRM test suite)."""
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


# ================================================================ TrainingNomination CRUD
class TestTrainingNominationListView:
    def test_list_200(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks

    def test_list_filter_by_status(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"status": "pending"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks

    def test_list_filter_by_nomination_type(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"nomination_type": "self"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks

    def test_list_filter_by_session(self, client_a, training_session_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"session": training_session_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks

    def test_list_filter_by_employee(self, client_a, employee_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"employee": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks

    def test_list_search_by_number(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"q": nomination_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks

    def test_list_has_choices_context(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"))
        assert "status_choices" in resp.context
        assert "nomination_type_choices" in resp.context
        assert "sessions" in resp.context
        assert "employees" in resp.context

    def test_bad_session_filter_does_not_500(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"session": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, nomination_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:trainingnomination_list"))


class TestTrainingNominationCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:trainingnomination_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingNomination
        resp = client_a.post(
            reverse("hrm:trainingnomination_create"), _nomination_post_data(training_session_a, employee_a))
        assert resp.status_code == 302
        nom = TrainingNomination.objects.filter(tenant=tenant_a, session=training_session_a, employee=employee_a).first()
        assert nom is not None
        assert nom.tenant_id == tenant_a.pk
        assert nom.number.startswith("NOM-")
        assert nom.status == "pending"

    def test_post_duplicate_rejected(self, client_a, training_session_a, employee_a, nomination_a):
        resp = client_a.post(
            reverse("hrm:trainingnomination_create"), _nomination_post_data(training_session_a, employee_a))
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()

    def test_form_has_no_status_number_approver_fields(self, client_a):
        resp = client_a.get(reverse("hrm:trainingnomination_create"))
        fields = resp.context["form"].fields
        assert "status" not in fields
        assert "number" not in fields
        assert "approver" not in fields
        assert "approved_at" not in fields
        assert "tenant" not in fields


class TestTrainingNominationDetailEditDelete:
    def test_detail_200(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_detail", args=[nomination_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_detail", args=[nomination_a.pk]))
        assert "obj" in resp.context
        assert "can_decide" in resp.context
        assert "is_admin" in resp.context

    def test_edit_get_200_when_pending(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_edit", args=[nomination_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_pending(self, client_a, nomination_a):
        nomination_a.status = "approved"
        nomination_a.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:trainingnomination_edit", args=[nomination_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingnomination_detail", args=[nomination_a.pk])

    def test_edit_post_updates_priority(self, client_a, nomination_a, training_session_a, employee_a):
        resp = client_a.post(
            reverse("hrm:trainingnomination_edit", args=[nomination_a.pk]),
            _nomination_post_data(training_session_a, employee_a, priority="high"),
        )
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.priority == "high"

    def test_delete_post_removes_when_pending(self, client_a, nomination_a):
        from apps.hrm.models import TrainingNomination
        pk = nomination_a.pk
        resp = client_a.post(reverse("hrm:trainingnomination_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TrainingNomination.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_approved(self, client_a, nomination_a):
        from apps.hrm.models import TrainingNomination
        nomination_a.status = "approved"
        nomination_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:trainingnomination_delete", args=[nomination_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingnomination_detail", args=[nomination_a.pk])
        assert TrainingNomination.objects.filter(pk=nomination_a.pk).exists()

    def test_delete_blocked_when_waitlisted(self, client_a, nomination_a):
        from apps.hrm.models import TrainingNomination
        nomination_a.status = "waitlisted"
        nomination_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:trainingnomination_delete", args=[nomination_a.pk]))
        assert resp.status_code == 302
        assert TrainingNomination.objects.filter(pk=nomination_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_delete", args=[nomination_a.pk]))
        assert resp.status_code == 405


# ================================================================ TrainingNomination workflow
class TestTrainingNominationApprove:
    def test_approve_by_admin_not_full_sets_approved(self, client_a, nomination_a):
        resp = client_a.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "approved"

    def test_approve_by_manager_sets_approved(self, tenant_a, employment_a, person_a2, employee_a2, nomination_a):
        employment_a.manager = person_a2
        employment_a.save(update_fields=["manager"])
        c = _client_for(person_a2, tenant_a, email="mgr_appr@acme.com", username="mgr_appr_acme")
        resp = c.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "approved"

    def test_approve_when_full_and_waitlist_enabled_sets_waitlisted(
        self, client_a, tenant_a, training_session_a, employee_a2, nomination_a
    ):
        from apps.hrm.models import TrainingNomination
        training_session_a.capacity = 1
        training_session_a.waitlist_enabled = True
        training_session_a.save(update_fields=["capacity", "waitlist_enabled"])
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2, status="approved")
        resp = client_a.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "waitlisted"

    def test_approve_when_full_and_waitlist_disabled_blocked(
        self, client_a, tenant_a, training_session_a, employee_a2, nomination_a
    ):
        from apps.hrm.models import TrainingNomination
        training_session_a.capacity = 1
        training_session_a.waitlist_enabled = False
        training_session_a.save(update_fields=["capacity", "waitlist_enabled"])
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2, status="approved")
        resp = client_a.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"  # unchanged

    def test_approve_blocked_when_not_pending(self, client_a, nomination_a):
        nomination_a.status = "rejected"
        nomination_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        nomination_a.refresh_from_db()
        assert nomination_a.status == "rejected"  # unchanged

    def test_approve_forbidden_for_non_manager_non_admin_non_nominee(
        self, tenant_a, employee_a2, nomination_a
    ):
        """Permission gate: a plain tenant user who is neither admin, the nominee's manager, nor the
        nominee themselves must be redirected with NO state change."""
        c = _client_for(employee_a2.party, tenant_a, email="outsider_appr@acme.com", username="outsider_appr_acme")
        resp = c.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"  # unchanged

    def test_approve_get_not_allowed(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 405


class TestTrainingNominationReject:
    def test_reject_by_admin_sets_rejected_with_reason(self, client_a, nomination_a):
        resp = client_a.post(
            reverse("hrm:trainingnomination_reject", args=[nomination_a.pk]),
            {"rejected_reason": "Budget constraints"})
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "rejected"
        assert nomination_a.rejected_reason == "Budget constraints"

    def test_reject_waitlisted_allowed(self, client_a, nomination_a):
        nomination_a.status = "waitlisted"
        nomination_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:trainingnomination_reject", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "rejected"

    def test_reject_blocked_when_approved(self, client_a, nomination_a):
        nomination_a.status = "approved"
        nomination_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:trainingnomination_reject", args=[nomination_a.pk]))
        nomination_a.refresh_from_db()
        assert nomination_a.status == "approved"  # unchanged

    def test_reject_forbidden_for_non_manager_non_admin_non_nominee(self, tenant_a, employee_a2, nomination_a):
        c = _client_for(employee_a2.party, tenant_a, email="outsider_rej@acme.com", username="outsider_rej_acme")
        resp = c.post(reverse("hrm:trainingnomination_reject", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"  # unchanged

    def test_reject_get_not_allowed(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_reject", args=[nomination_a.pk]))
        assert resp.status_code == 405


class TestTrainingNominationWaitlist:
    def test_waitlist_by_admin_sets_waitlisted(self, client_a, nomination_a):
        resp = client_a.post(reverse("hrm:trainingnomination_waitlist", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "waitlisted"

    def test_waitlist_forbidden_for_non_admin(self, member_client, nomination_a):
        resp = member_client.post(reverse("hrm:trainingnomination_waitlist", args=[nomination_a.pk]))
        assert resp.status_code == 403
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"  # unchanged

    def test_waitlist_blocked_when_not_pending(self, client_a, nomination_a):
        nomination_a.status = "approved"
        nomination_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:trainingnomination_waitlist", args=[nomination_a.pk]))
        nomination_a.refresh_from_db()
        assert nomination_a.status == "approved"  # unchanged

    def test_waitlist_get_not_allowed(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_waitlist", args=[nomination_a.pk]))
        assert resp.status_code == 405


class TestTrainingNominationCancel:
    def test_cancel_by_admin_sets_cancelled(self, client_a, nomination_a):
        resp = client_a.post(
            reverse("hrm:trainingnomination_cancel", args=[nomination_a.pk]), {"cancelled_reason": "No longer needed"})
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "cancelled"
        assert nomination_a.cancelled_reason == "No longer needed"

    def test_cancel_by_nominator(self, tenant_a, training_session_a, employee_a, employee_a2):
        from apps.hrm.models import TrainingNomination
        nom = TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a,
            nominated_by=employee_a2, nomination_type="manager")
        c = _client_for(employee_a2.party, tenant_a, email="nominator@acme.com", username="nominator_acme")
        resp = c.post(reverse("hrm:trainingnomination_cancel", args=[nom.pk]))
        assert resp.status_code == 302
        nom.refresh_from_db()
        assert nom.status == "cancelled"

    def test_cancel_by_manager(self, tenant_a, employment_a, person_a2, employee_a2, nomination_a):
        employment_a.manager = person_a2
        employment_a.save(update_fields=["manager"])
        c = _client_for(person_a2, tenant_a, email="mgr_cancel@acme.com", username="mgr_cancel_acme")
        resp = c.post(reverse("hrm:trainingnomination_cancel", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "cancelled"

    def test_cancel_forbidden_for_plain_nominee_who_is_not_nominator(self, tenant_a, employee_a, nomination_a):
        """The nominee alone (self-nominated, nominated_by=None) is NOT permitted to cancel — that's
        what withdraw is for."""
        c = _client_for(employee_a.party, tenant_a, email="nominee_cancel@acme.com", username="nominee_cancel_acme")
        resp = c.post(reverse("hrm:trainingnomination_cancel", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"  # unchanged

    def test_cancel_blocked_when_rejected(self, client_a, nomination_a):
        nomination_a.status = "rejected"
        nomination_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:trainingnomination_cancel", args=[nomination_a.pk]))
        nomination_a.refresh_from_db()
        assert nomination_a.status == "rejected"  # unchanged

    def test_cancel_get_not_allowed(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_cancel", args=[nomination_a.pk]))
        assert resp.status_code == 405


class TestTrainingNominationWithdraw:
    def test_withdraw_by_nominee_sets_withdrawn(self, tenant_a, employee_a, nomination_a):
        c = _client_for(employee_a.party, tenant_a, email="nominee_wd@acme.com", username="nominee_wd_acme")
        resp = c.post(reverse("hrm:trainingnomination_withdraw", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "withdrawn"

    def test_withdraw_by_admin_forbidden(self, client_a, nomination_a):
        """Only the nominee may withdraw — an admin (who is not the nominee) is blocked."""
        resp = client_a.post(reverse("hrm:trainingnomination_withdraw", args=[nomination_a.pk]))
        assert resp.status_code == 302
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"  # unchanged

    def test_withdraw_blocked_when_rejected(self, tenant_a, employee_a, nomination_a):
        nomination_a.status = "rejected"
        nomination_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="nominee_wd2@acme.com", username="nominee_wd2_acme")
        c.post(reverse("hrm:trainingnomination_withdraw", args=[nomination_a.pk]))
        nomination_a.refresh_from_db()
        assert nomination_a.status == "rejected"  # unchanged

    def test_withdraw_get_not_allowed(self, client_a, nomination_a):
        resp = client_a.get(reverse("hrm:trainingnomination_withdraw", args=[nomination_a.pk]))
        assert resp.status_code == 405


# ================================================================ TrainingAttendance CRUD
class TestTrainingAttendanceListView:
    def test_list_200(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_attendance_a.pk in pks

    def test_list_filter_by_attendance_status(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"), {"attendance_status": "present"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_attendance_a.pk in pks

    def test_list_filter_by_completion_status(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"), {"completion_status": "not_completed"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_attendance_a.pk in pks

    def test_list_filter_by_session(self, client_a, training_session_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"), {"session": training_session_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_attendance_a.pk in pks

    def test_list_has_choices_context(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"))
        assert "attendance_status_choices" in resp.context
        assert "completion_status_choices" in resp.context
        assert "sessions" in resp.context
        assert "employees" in resp.context

    def test_bad_completion_status_filter_does_not_500(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"), {"completion_status": "bogus"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, training_attendance_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:trainingattendance_list"))


class TestTrainingAttendanceCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:trainingattendance_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingAttendance
        resp = client_a.post(
            reverse("hrm:trainingattendance_create"), _attendance_post_data(training_session_a, employee_a))
        assert resp.status_code == 302
        att = TrainingAttendance.objects.filter(
            tenant=tenant_a, session=training_session_a, employee=employee_a).first()
        assert att is not None
        assert att.tenant_id == tenant_a.pk

    def test_post_duplicate_rejected(self, client_a, training_session_a, employee_a, training_attendance_a):
        resp = client_a.post(
            reverse("hrm:trainingattendance_create"), _attendance_post_data(training_session_a, employee_a))
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()

    def test_post_check_out_before_check_in_rejected(self, client_a, tenant_a, training_session_a, employee_a2):
        from apps.hrm.models import TrainingAttendance
        resp = client_a.post(
            reverse("hrm:trainingattendance_create"),
            _attendance_post_data(
                training_session_a, employee_a2,
                check_in_at="2026-07-20T10:00", check_out_at="2026-07-20T09:00"),
        )
        assert resp.status_code == 200
        assert not TrainingAttendance.objects.filter(tenant=tenant_a, employee=employee_a2).exists()

    def test_form_has_no_tenant_field(self, client_a):
        resp = client_a.get(reverse("hrm:trainingattendance_create"))
        assert "tenant" not in resp.context["form"].fields


class TestTrainingAttendanceDetailEditDelete:
    def test_detail_200(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_detail", args=[training_attendance_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_detail", args=[training_attendance_a.pk]))
        assert "obj" in resp.context
        assert "is_admin" in resp.context
        assert "current_profile_id" in resp.context
        assert "feedback" in resp.context

    def test_detail_has_linked_feedback(self, client_a, training_attendance_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingattendance_detail", args=[training_attendance_a.pk]))
        assert resp.context["feedback"].pk == training_feedback_a.pk

    def test_edit_get_200(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_edit", args=[training_attendance_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_completion_status(self, client_a, training_attendance_a, training_session_a, employee_a):
        resp = client_a.post(
            reverse("hrm:trainingattendance_edit", args=[training_attendance_a.pk]),
            _attendance_post_data(training_session_a, employee_a, completion_status="completed"),
        )
        assert resp.status_code == 302
        training_attendance_a.refresh_from_db()
        assert training_attendance_a.completion_status == "completed"

    def test_delete_post_removes_when_no_feedback_or_certificate(self, client_a, tenant_a, training_session_a, employee_a2):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance.objects.create(tenant=tenant_a, session=training_session_a, employee=employee_a2)
        resp = client_a.post(reverse("hrm:trainingattendance_delete", args=[att.pk]))
        assert resp.status_code == 302
        assert not TrainingAttendance.objects.filter(pk=att.pk).exists()

    def test_delete_blocked_when_feedback_exists(self, client_a, tenant_a, training_attendance_a, training_feedback_a):
        from apps.hrm.models import TrainingAttendance
        resp = client_a.post(reverse("hrm:trainingattendance_delete", args=[training_attendance_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingattendance_detail", args=[training_attendance_a.pk])
        assert TrainingAttendance.objects.filter(pk=training_attendance_a.pk).exists()

    def test_delete_blocked_when_certificate_exists(self, client_a, tenant_a, employee_a, training_course_a, training_attendance_a):
        from apps.hrm.models import TrainingAttendance, TrainingCertificate
        TrainingCertificate.objects.create(
            tenant=tenant_a, employee=employee_a, course=training_course_a,
            source_attendance=training_attendance_a)
        resp = client_a.post(reverse("hrm:trainingattendance_delete", args=[training_attendance_a.pk]))
        assert resp.status_code == 302
        assert TrainingAttendance.objects.filter(pk=training_attendance_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingattendance_delete", args=[training_attendance_a.pk]))
        assert resp.status_code == 405


class TestTrainingSessionDeleteProtectedByNominationOrAttendance:
    def test_delete_blocked_when_nomination_exists(self, client_a, training_session_a, nomination_a):
        from apps.hrm.models import TrainingSession
        resp = client_a.post(reverse("hrm:trainingsession_delete", args=[training_session_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingsession_detail", args=[training_session_a.pk])
        assert TrainingSession.objects.filter(pk=training_session_a.pk).exists()

    def test_delete_blocked_when_attendance_exists(self, client_a, training_session_a, training_attendance_a):
        from apps.hrm.models import TrainingSession
        resp = client_a.post(reverse("hrm:trainingsession_delete", args=[training_session_a.pk]))
        assert resp.status_code == 302
        assert TrainingSession.objects.filter(pk=training_session_a.pk).exists()


# ================================================================ TrainingFeedback (ownership)
class TestTrainingFeedbackNestedCreate:
    def test_get_200_by_attendee(self, tenant_a, employee_a, training_attendance_a):
        c = _client_for(employee_a.party, tenant_a, email="attendee_fb@acme.com", username="attendee_fb_acme")
        resp = c.get(reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]))
        assert resp.status_code == 200

    def test_get_200_by_admin(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_by_attendee_and_redirects_to_attendance_detail(
        self, tenant_a, employee_a, training_attendance_a
    ):
        from apps.hrm.models import TrainingFeedback
        c = _client_for(employee_a.party, tenant_a, email="attendee_fb2@acme.com", username="attendee_fb2_acme")
        resp = c.post(
            reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]), _feedback_post_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingattendance_detail", args=[training_attendance_a.pk])
        fb = TrainingFeedback.objects.filter(tenant=tenant_a, attendance=training_attendance_a).first()
        assert fb is not None
        assert fb.tenant_id == tenant_a.pk

    def test_post_creates_by_admin(self, client_a, tenant_a, training_attendance_a):
        from apps.hrm.models import TrainingFeedback
        resp = client_a.post(
            reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]), _feedback_post_data())
        assert resp.status_code == 302
        assert TrainingFeedback.objects.filter(tenant=tenant_a, attendance=training_attendance_a).exists()

    def test_create_blocked_for_a_different_non_admin_employee(
        self, tenant_a, employee_a2, training_attendance_a
    ):
        """training_attendance_a belongs to employee_a — a different non-admin (employee_a2) must be
        blocked from leaving feedback for it (the security fix pin)."""
        from apps.hrm.models import TrainingFeedback
        c = _client_for(employee_a2.party, tenant_a, email="other_fb@acme.com", username="other_fb_acme")
        resp = c.post(
            reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]), _feedback_post_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingattendance_detail", args=[training_attendance_a.pk])
        assert not TrainingFeedback.objects.filter(tenant=tenant_a, attendance=training_attendance_a).exists()

    def test_post_duplicate_rejected(self, tenant_a, employee_a, training_attendance_a, training_feedback_a):
        c = _client_for(employee_a.party, tenant_a, email="attendee_fb3@acme.com", username="attendee_fb3_acme")
        resp = c.post(
            reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]), _feedback_post_data())
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()

    def test_form_has_no_tenant_or_attendance_field(self, client_a, training_attendance_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]))
        fields = resp.context["form"].fields
        assert "tenant" not in fields
        assert "attendance" not in fields


class TestTrainingFeedbackListView:
    def test_list_200(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_feedback_a.pk in pks

    def test_list_filter_by_would_recommend(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"), {"would_recommend": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_feedback_a.pk in pks

    def test_list_filter_by_session(self, client_a, training_session_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"), {"session": training_session_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_feedback_a.pk in pks

    def test_list_has_choices_context(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"))
        assert "sessions" in resp.context
        assert "is_admin" in resp.context
        assert "current_profile_id" in resp.context

    def test_bad_session_filter_does_not_500(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"), {"session": "abc"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, training_feedback_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:trainingfeedback_list"))


class TestTrainingFeedbackAnonymityMasking:
    def test_list_masks_attendee_for_non_admin(self, tenant_a, employee_a2, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        c = _client_for(employee_a2.party, tenant_a, email="viewer_fb@acme.com", username="viewer_fb_acme")
        resp = c.get(reverse("hrm:trainingfeedback_list"))
        assert b"Alice Smith" not in resp.content
        assert b"Anonymous" in resp.content

    def test_list_shows_attendee_for_admin(self, client_a, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:trainingfeedback_list"))
        assert b"Alice Smith" in resp.content

    def test_detail_masks_attendee_for_non_admin(self, tenant_a, employee_a2, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        c = _client_for(employee_a2.party, tenant_a, email="viewer_fb2@acme.com", username="viewer_fb2_acme")
        resp = c.get(reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk]))
        assert b"Alice Smith" not in resp.content
        assert b"Anonymous" in resp.content

    def test_detail_shows_attendee_for_admin(self, client_a, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk]))
        assert b"Alice Smith" in resp.content

    def test_detail_shows_attendee_to_the_attendee_themselves(self, tenant_a, employee_a, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        c = _client_for(employee_a.party, tenant_a, email="self_fb@acme.com", username="self_fb_acme")
        resp = c.get(reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk]))
        assert b"Alice Smith" in resp.content


class TestTrainingFeedbackEditDelete:
    def test_edit_get_200_by_attendee(self, tenant_a, employee_a, training_feedback_a):
        c = _client_for(employee_a.party, tenant_a, email="attendee_edit@acme.com", username="attendee_edit_acme")
        resp = c.get(reverse("hrm:trainingfeedback_edit", args=[training_feedback_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_by_admin(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_edit", args=[training_feedback_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_for_a_different_non_admin_employee(self, tenant_a, employee_a2, training_feedback_a):
        c = _client_for(employee_a2.party, tenant_a, email="other_edit@acme.com", username="other_edit_acme")
        resp = c.get(reverse("hrm:trainingfeedback_edit", args=[training_feedback_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk])

    def test_edit_post_blocked_for_a_different_non_admin_employee_does_not_mutate(
        self, tenant_a, employee_a2, training_feedback_a
    ):
        c = _client_for(employee_a2.party, tenant_a, email="other_edit2@acme.com", username="other_edit2_acme")
        original_comments = training_feedback_a.comments
        resp = c.post(
            reverse("hrm:trainingfeedback_edit", args=[training_feedback_a.pk]),
            _feedback_post_data(comments="hacked"))
        assert resp.status_code == 302
        training_feedback_a.refresh_from_db()
        assert training_feedback_a.comments == original_comments

    def test_edit_post_updates_comments_by_attendee(self, tenant_a, employee_a, training_feedback_a):
        c = _client_for(employee_a.party, tenant_a, email="attendee_edit2@acme.com", username="attendee_edit2_acme")
        resp = c.post(
            reverse("hrm:trainingfeedback_edit", args=[training_feedback_a.pk]),
            _feedback_post_data(comments="Great session"))
        assert resp.status_code == 302
        training_feedback_a.refresh_from_db()
        assert training_feedback_a.comments == "Great session"

    def test_delete_by_attendee(self, tenant_a, employee_a, training_feedback_a):
        from apps.hrm.models import TrainingFeedback
        pk = training_feedback_a.pk
        c = _client_for(employee_a.party, tenant_a, email="attendee_del@acme.com", username="attendee_del_acme")
        resp = c.post(reverse("hrm:trainingfeedback_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TrainingFeedback.objects.filter(pk=pk).exists()

    def test_delete_by_admin(self, client_a, training_feedback_a):
        from apps.hrm.models import TrainingFeedback
        pk = training_feedback_a.pk
        resp = client_a.post(reverse("hrm:trainingfeedback_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TrainingFeedback.objects.filter(pk=pk).exists()

    def test_delete_blocked_for_a_different_non_admin_employee(self, tenant_a, employee_a2, training_feedback_a):
        from apps.hrm.models import TrainingFeedback
        c = _client_for(employee_a2.party, tenant_a, email="other_del@acme.com", username="other_del_acme")
        resp = c.post(reverse("hrm:trainingfeedback_delete", args=[training_feedback_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk])
        assert TrainingFeedback.objects.filter(pk=training_feedback_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, training_feedback_a):
        resp = client_a.get(reverse("hrm:trainingfeedback_delete", args=[training_feedback_a.pk]))
        assert resp.status_code == 405


# ================================================================ TrainingCertificate list/search/filter
class TestTrainingCertificateListView:
    def test_list_200(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks

    def test_list_filter_by_status(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"status": "issued"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks

    def test_list_filter_by_course(self, client_a, cert_course_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"course": cert_course_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks

    def test_list_filter_by_employee(self, client_a, employee_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"employee": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks

    def test_list_search_by_number(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"q": training_certificate_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks

    def test_list_search_by_verification_code(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"q": training_certificate_a.verification_code})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks

    def test_list_has_choices_context(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"))
        assert "status_choices" in resp.context
        assert "courses" in resp.context
        assert "employees" in resp.context

    def test_bad_course_filter_does_not_500(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"course": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, training_certificate_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:trainingcertificate_list"))


# ================================================================ TrainingCertificate admin-gating
class TestTrainingCertificateAdminGating:
    def test_create_get_403_for_non_admin(self, member_client):
        resp = member_client.get(reverse("hrm:trainingcertificate_create"))
        assert resp.status_code == 403

    def test_create_post_403_for_non_admin_no_row_created(self, member_client, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        resp = member_client.post(
            reverse("hrm:trainingcertificate_create"), _certificate_post_data(employee_a, cert_course_a))
        assert resp.status_code == 403
        assert not TrainingCertificate.objects.filter(tenant=tenant_a, employee=employee_a, course=cert_course_a).exists()

    def test_create_allowed_for_admin(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        resp = client_a.post(
            reverse("hrm:trainingcertificate_create"), _certificate_post_data(employee_a, cert_course_a))
        assert resp.status_code == 302
        cert = TrainingCertificate.objects.filter(tenant=tenant_a, employee=employee_a, course=cert_course_a).first()
        assert cert is not None
        assert cert.number.startswith("CERT-")

    def test_edit_get_403_for_non_admin(self, member_client, training_certificate_a):
        resp = member_client.get(reverse("hrm:trainingcertificate_edit", args=[training_certificate_a.pk]))
        assert resp.status_code == 403

    def test_edit_post_403_for_non_admin_no_change(self, member_client, training_certificate_a):
        original_title = training_certificate_a.title
        resp = member_client.post(
            reverse("hrm:trainingcertificate_edit", args=[training_certificate_a.pk]),
            _certificate_post_data(training_certificate_a.employee, training_certificate_a.course, title="hacked"))
        assert resp.status_code == 403
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.title == original_title

    def test_edit_allowed_for_admin(self, client_a, training_certificate_a):
        resp = client_a.post(
            reverse("hrm:trainingcertificate_edit", args=[training_certificate_a.pk]),
            _certificate_post_data(
                training_certificate_a.employee, training_certificate_a.course, title="Renamed Cert"))
        assert resp.status_code == 302
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.title == "Renamed Cert"

    def test_edit_blocked_when_revoked_even_for_admin(self, client_a, training_certificate_a):
        training_certificate_a.status = "revoked"
        training_certificate_a.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:trainingcertificate_edit", args=[training_certificate_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingcertificate_detail", args=[training_certificate_a.pk])

    def test_delete_403_for_non_admin(self, member_client, training_certificate_a):
        training_certificate_a.status = "revoked"
        training_certificate_a.save(update_fields=["status"])
        from apps.hrm.models import TrainingCertificate
        resp = member_client.post(reverse("hrm:trainingcertificate_delete", args=[training_certificate_a.pk]))
        assert resp.status_code == 403
        assert TrainingCertificate.objects.filter(pk=training_certificate_a.pk).exists()

    def test_delete_allowed_for_admin_when_revoked(self, client_a, training_certificate_a):
        from apps.hrm.models import TrainingCertificate
        training_certificate_a.status = "revoked"
        training_certificate_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:trainingcertificate_delete", args=[training_certificate_a.pk]))
        assert resp.status_code == 302
        assert not TrainingCertificate.objects.filter(pk=training_certificate_a.pk).exists()

    def test_delete_blocked_while_issued(self, client_a, training_certificate_a):
        from apps.hrm.models import TrainingCertificate
        resp = client_a.post(reverse("hrm:trainingcertificate_delete", args=[training_certificate_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingcertificate_detail", args=[training_certificate_a.pk])
        assert TrainingCertificate.objects.filter(pk=training_certificate_a.pk).exists()

    def test_revoke_403_for_non_admin(self, member_client, training_certificate_a):
        resp = member_client.post(reverse("hrm:trainingcertificate_revoke", args=[training_certificate_a.pk]))
        assert resp.status_code == 403
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.status == "issued"

    def test_revoke_allowed_for_admin(self, client_a, training_certificate_a):
        resp = client_a.post(
            reverse("hrm:trainingcertificate_revoke", args=[training_certificate_a.pk]),
            {"revoked_reason": "Issued in error"})
        assert resp.status_code == 302
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.status == "revoked"
        assert training_certificate_a.revoked_reason == "Issued in error"

    def test_revoke_blocked_when_already_revoked(self, client_a, training_certificate_a):
        training_certificate_a.status = "revoked"
        training_certificate_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:trainingcertificate_revoke", args=[training_certificate_a.pk]))
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.status == "revoked"  # unchanged, no error

    def test_issue_from_attendance_get_403_for_non_admin(self, member_client, tenant_a, employee_a, cert_course_a, training_attendance_a):
        resp = member_client.get(
            reverse("hrm:trainingcertificate_issue_from_attendance", args=[training_attendance_a.pk]))
        assert resp.status_code == 403

    def test_issue_from_progress_get_403_for_non_admin(self, member_client, learning_progress_a):
        resp = member_client.get(
            reverse("hrm:trainingcertificate_issue_from_progress", args=[learning_progress_a.pk]))
        assert resp.status_code == 403

    def test_list_view_200_for_non_admin_read_only(self, member_client, training_certificate_a):
        """The list itself is view-only for a non-admin (no tenant_admin_required on the list)."""
        resp = member_client.get(reverse("hrm:trainingcertificate_list"))
        assert resp.status_code == 200
        assert resp.context["is_admin"] is False


# ================================================================ TrainingCertificate issue-from routes
class TestIssueFromAttendance:
    def test_issue_creates_certificate(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingAttendance, TrainingCertificate, TrainingSession
        session = TrainingSession.objects.create(
            tenant=tenant_a, course=cert_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 7, 1, 9, 0), end_datetime=_dt(2026, 7, 1, 17, 0),
            venue_name="Room 1",
        )
        att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=session, employee=employee_a, completion_status="completed")
        # The route pre-fills the form on GET; POSTing the (now-filled) form is what actually issues it.
        resp = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_attendance", args=[att.pk]),
            _certificate_post_data(employee_a, cert_course_a, source_attendance=att.pk),
        )
        assert resp.status_code == 302
        cert = TrainingCertificate.objects.filter(tenant=tenant_a, source_attendance=att).first()
        assert cert is not None
        assert cert.employee_id == employee_a.pk
        assert cert.course_id == cert_course_a.pk

    def test_issue_blocked_when_not_completed(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingAttendance, TrainingCertificate, TrainingSession
        session = TrainingSession.objects.create(
            tenant=tenant_a, course=cert_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 7, 2, 9, 0), end_datetime=_dt(2026, 7, 2, 17, 0),
            venue_name="Room 2",
        )
        att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=session, employee=employee_a, completion_status="not_completed")
        resp = client_a.post(reverse("hrm:trainingcertificate_issue_from_attendance", args=[att.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingattendance_detail", args=[att.pk])
        assert not TrainingCertificate.objects.filter(tenant=tenant_a, source_attendance=att).exists()

    def test_issue_blocked_when_course_not_certification(self, client_a, tenant_a, employee_a, training_session_a):
        from apps.hrm.models import TrainingAttendance, TrainingCertificate
        att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a, completion_status="completed")
        resp = client_a.post(reverse("hrm:trainingcertificate_issue_from_attendance", args=[att.pk]))
        assert resp.status_code == 302
        assert not TrainingCertificate.objects.filter(tenant=tenant_a, source_attendance=att).exists()

    def test_duplicate_issuance_from_same_attendance_creates_only_one(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingAttendance, TrainingCertificate, TrainingSession
        session = TrainingSession.objects.create(
            tenant=tenant_a, course=cert_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 7, 3, 9, 0), end_datetime=_dt(2026, 7, 3, 17, 0),
            venue_name="Room 3",
        )
        att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=session, employee=employee_a, completion_status="completed")
        first = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_attendance", args=[att.pk]),
            _certificate_post_data(employee_a, cert_course_a, source_attendance=att.pk),
        )
        assert first.status_code == 302
        assert TrainingCertificate.objects.filter(tenant=tenant_a, source_attendance=att).count() == 1
        existing = TrainingCertificate.objects.get(tenant=tenant_a, source_attendance=att)
        # The 2nd attempt short-circuits on the existing-cert check BEFORE touching the form, so an
        # empty POST body is enough to prove it redirects to the existing cert without re-issuing.
        second = client_a.post(reverse("hrm:trainingcertificate_issue_from_attendance", args=[att.pk]))
        assert second.status_code == 302
        assert second["Location"] == reverse("hrm:trainingcertificate_detail", args=[existing.pk])
        assert TrainingCertificate.objects.filter(tenant=tenant_a, source_attendance=att).count() == 1


class TestIssueFromProgress:
    def test_issue_creates_certificate(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, status="completed")
        # The route pre-fills the form on GET; POSTing the (now-filled) form is what actually issues it.
        resp = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_progress", args=[progress.pk]),
            _certificate_post_data(employee_a, cert_course_a, source_progress=progress.pk),
        )
        assert resp.status_code == 302
        cert = TrainingCertificate.objects.filter(tenant=tenant_a, source_progress=progress).first()
        assert cert is not None
        assert cert.employee_id == employee_a.pk

    def test_issue_blocked_when_not_completed(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, status="in_progress")
        resp = client_a.post(reverse("hrm:trainingcertificate_issue_from_progress", args=[progress.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:learningprogress_detail", args=[progress.pk])
        assert not TrainingCertificate.objects.filter(tenant=tenant_a, source_progress=progress).exists()

    def test_issue_blocked_when_course_not_certification(self, client_a, learning_progress_a):
        from apps.hrm.models import TrainingCertificate
        learning_progress_a.status = "completed"
        learning_progress_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_progress", args=[learning_progress_a.pk]))
        assert resp.status_code == 302
        assert not TrainingCertificate.objects.filter(source_progress=learning_progress_a).exists()

    def test_duplicate_issuance_from_same_progress_creates_only_one(self, client_a, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, status="completed")
        first = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_progress", args=[progress.pk]),
            _certificate_post_data(employee_a, cert_course_a, source_progress=progress.pk),
        )
        assert first.status_code == 302
        existing = TrainingCertificate.objects.get(tenant=tenant_a, source_progress=progress)
        # The 2nd attempt short-circuits on the existing-cert check BEFORE touching the form.
        second = client_a.post(reverse("hrm:trainingcertificate_issue_from_progress", args=[progress.pk]))
        assert second["Location"] == reverse("hrm:trainingcertificate_detail", args=[existing.pk])
        assert TrainingCertificate.objects.filter(tenant=tenant_a, source_progress=progress).count() == 1


class TestTrainingCertificateDetailAndPrint:
    def test_detail_200(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_detail", args=[training_certificate_a.pk]))
        assert resp.status_code == 200

    def test_print_200_for_logged_in_user(self, client_a, training_certificate_a):
        resp = client_a.get(reverse("hrm:trainingcertificate_print", args=[training_certificate_a.pk]))
        assert resp.status_code == 200

    def test_print_allowed_for_non_admin_view_only(self, member_client, training_certificate_a):
        resp = member_client.get(reverse("hrm:trainingcertificate_print", args=[training_certificate_a.pk]))
        assert resp.status_code == 200


# ================================================================ Training Budget (computed view)
class TestTrainingBudget:
    def test_renders_200(self, client_a):
        resp = client_a.get(reverse("hrm:training_budget"))
        assert resp.status_code == 200

    def test_bad_year_does_not_500(self, client_a):
        resp = client_a.get(reverse("hrm:training_budget"), {"year": "abc"})
        assert resp.status_code == 200

    def test_context_keys(self, client_a):
        resp = client_a.get(reverse("hrm:training_budget"))
        assert "year" in resp.context
        assert "years" in resp.context
        assert "total_estimated" in resp.context
        assert "total_actual" in resp.context
        assert "total_allocated" in resp.context
        assert "by_course" in resp.context

    def test_aggregates_session_costs_for_selected_year(self, client_a, tenant_a, training_session_a):
        from decimal import Decimal
        training_session_a.estimated_cost = Decimal("1000")
        training_session_a.actual_cost = Decimal("900")
        training_session_a.save(update_fields=["estimated_cost", "actual_cost"])
        resp = client_a.get(reverse("hrm:training_budget"), {"year": 2026})
        assert resp.context["total_estimated"] == Decimal("1000")
        assert resp.context["total_actual"] == Decimal("900")

    def test_anonymous_redirected(self, client):
        resp = client.get(reverse("hrm:training_budget"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
