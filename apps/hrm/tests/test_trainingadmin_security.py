"""Security tests for HRM 3.24 Training Administration: anonymous redirect-to-login, cross-tenant
IDOR (404) on TrainingNomination/TrainingAttendance/TrainingFeedback/TrainingCertificate
detail/edit/delete + workflow actions (+ list isolation, + row survives the attempt), nested-create
(feedback) and issue-from-* routes with a cross-tenant parent pk -> 404, feedback anonymity masking
for a non-admin viewer, certificate print login-gating + tenant scoping + no public verify endpoint,
tenant is always server-set (never smuggled via POST data, and blocked outright when
request.tenant is None), and CSRF enforcement on the POST-only actions. Mirrors
test_training_security.py / test_lms_security.py conventions; client_a is the tenant admin."""
import pytest
from django.test import Client
from django.urls import NoReverseMatch, reverse

pytestmark = pytest.mark.django_db


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


# ================================================================ Anonymous -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name", [
        "hrm:trainingnomination_list", "hrm:trainingnomination_create",
        "hrm:trainingattendance_list", "hrm:trainingattendance_create",
        "hrm:trainingfeedback_list", "hrm:trainingcertificate_list",
        "hrm:trainingcertificate_create", "hrm:training_budget",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_and_edit_pages(
        self, client, nomination_a, training_attendance_a, training_feedback_a, training_certificate_a
    ):
        for url_name, pk in [
            ("hrm:trainingnomination_detail", nomination_a.pk),
            ("hrm:trainingnomination_edit", nomination_a.pk),
            ("hrm:trainingattendance_detail", training_attendance_a.pk),
            ("hrm:trainingattendance_edit", training_attendance_a.pk),
            ("hrm:trainingfeedback_detail", training_feedback_a.pk),
            ("hrm:trainingfeedback_edit", training_feedback_a.pk),
            ("hrm:trainingcertificate_detail", training_certificate_a.pk),
            ("hrm:trainingcertificate_edit", training_certificate_a.pk),
            ("hrm:trainingcertificate_print", training_certificate_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_delete(
        self, client, nomination_a, training_attendance_a, training_feedback_a, training_certificate_a
    ):
        for url_name, pk in [
            ("hrm:trainingnomination_delete", nomination_a.pk),
            ("hrm:trainingattendance_delete", training_attendance_a.pk),
            ("hrm:trainingfeedback_delete", training_feedback_a.pk),
            ("hrm:trainingcertificate_delete", training_certificate_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_workflow_actions(self, client, nomination_a, training_certificate_a):
        for url_name, pk in [
            ("hrm:trainingnomination_approve", nomination_a.pk),
            ("hrm:trainingnomination_reject", nomination_a.pk),
            ("hrm:trainingnomination_waitlist", nomination_a.pk),
            ("hrm:trainingnomination_cancel", nomination_a.pk),
            ("hrm:trainingnomination_withdraw", nomination_a.pk),
            ("hrm:trainingcertificate_revoke", training_certificate_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_redirected_on_nested_create(self, client, training_attendance_a):
        resp = client.get(reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_issue_from_routes(self, client, training_attendance_a, learning_progress_a):
        for url_name, pk in [
            ("hrm:trainingcertificate_issue_from_attendance", training_attendance_a.pk),
            ("hrm:trainingcertificate_issue_from_progress", learning_progress_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ Cross-tenant IDOR: TrainingNomination
class TestTrainingNominationIDOR:
    def test_detail_cross_tenant_404(self, client_a, nomination_b):
        resp = client_a.get(reverse("hrm:trainingnomination_detail", args=[nomination_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, nomination_b):
        resp = client_a.get(reverse("hrm:trainingnomination_edit", args=[nomination_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, nomination_b):
        resp = client_a.post(
            reverse("hrm:trainingnomination_edit", args=[nomination_b.pk]),
            _nomination_post_data(nomination_b.session, nomination_b.employee, priority="high"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, nomination_b):
        original_priority = nomination_b.priority
        client_a.post(
            reverse("hrm:trainingnomination_edit", args=[nomination_b.pk]),
            _nomination_post_data(nomination_b.session, nomination_b.employee, priority="high"),
        )
        nomination_b.refresh_from_db()
        assert nomination_b.priority == original_priority

    def test_delete_cross_tenant_404(self, client_a, nomination_b):
        from apps.hrm.models import TrainingNomination
        resp = client_a.post(reverse("hrm:trainingnomination_delete", args=[nomination_b.pk]))
        assert resp.status_code == 404
        assert TrainingNomination.objects.filter(pk=nomination_b.pk).exists()

    def test_list_excludes_b_rows(self, client_a, nomination_a, nomination_b):
        resp = client_a.get(reverse("hrm:trainingnomination_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert nomination_a.pk in pks
        assert nomination_b.pk not in pks

    @pytest.mark.parametrize("url_name", [
        "hrm:trainingnomination_approve", "hrm:trainingnomination_reject",
        "hrm:trainingnomination_waitlist", "hrm:trainingnomination_cancel",
        "hrm:trainingnomination_withdraw",
    ])
    def test_workflow_action_cross_tenant_404(self, client_a, nomination_b, url_name):
        resp = client_a.post(reverse(url_name, args=[nomination_b.pk]))
        assert resp.status_code == 404

    def test_workflow_action_cross_tenant_does_not_mutate_status(self, client_a, nomination_b):
        original_status = nomination_b.status
        client_a.post(reverse("hrm:trainingnomination_approve", args=[nomination_b.pk]))
        nomination_b.refresh_from_db()
        assert nomination_b.status == original_status


# ================================================================ Cross-tenant IDOR: TrainingAttendance
class TestTrainingAttendanceIDOR:
    def test_detail_cross_tenant_404(self, client_a, training_attendance_b):
        resp = client_a.get(reverse("hrm:trainingattendance_detail", args=[training_attendance_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, training_attendance_b):
        resp = client_a.get(reverse("hrm:trainingattendance_edit", args=[training_attendance_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, training_attendance_b):
        resp = client_a.post(
            reverse("hrm:trainingattendance_edit", args=[training_attendance_b.pk]),
            _attendance_post_data(training_attendance_b.session, training_attendance_b.employee,
                                   completion_status="completed"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, training_attendance_b):
        original = training_attendance_b.completion_status
        client_a.post(
            reverse("hrm:trainingattendance_edit", args=[training_attendance_b.pk]),
            _attendance_post_data(training_attendance_b.session, training_attendance_b.employee,
                                   completion_status="completed"),
        )
        training_attendance_b.refresh_from_db()
        assert training_attendance_b.completion_status == original

    def test_delete_cross_tenant_404(self, client_a, training_attendance_b):
        from apps.hrm.models import TrainingAttendance
        resp = client_a.post(reverse("hrm:trainingattendance_delete", args=[training_attendance_b.pk]))
        assert resp.status_code == 404
        assert TrainingAttendance.objects.filter(pk=training_attendance_b.pk).exists()

    def test_list_excludes_b_rows(self, client_a, training_attendance_a, training_attendance_b):
        resp = client_a.get(reverse("hrm:trainingattendance_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_attendance_a.pk in pks
        assert training_attendance_b.pk not in pks

    def test_nested_feedback_create_cross_tenant_attendance_pk_404(self, client_a, training_attendance_b):
        resp = client_a.get(reverse("hrm:trainingfeedback_create", args=[training_attendance_b.pk]))
        assert resp.status_code == 404

    def test_nested_feedback_create_post_cross_tenant_attendance_pk_404(
        self, client_a, tenant_a, training_attendance_b
    ):
        from apps.hrm.models import TrainingFeedback
        resp = client_a.post(
            reverse("hrm:trainingfeedback_create", args=[training_attendance_b.pk]), _feedback_post_data())
        assert resp.status_code == 404
        assert not TrainingFeedback.objects.filter(tenant=tenant_a, attendance_id=training_attendance_b.pk).exists()

    def test_issue_from_attendance_cross_tenant_pk_404(self, client_a, training_attendance_b):
        resp = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_attendance", args=[training_attendance_b.pk]))
        assert resp.status_code == 404


# ================================================================ Cross-tenant IDOR: TrainingFeedback
class TestTrainingFeedbackIDOR:
    def test_detail_cross_tenant_404(self, client_a, training_feedback_b):
        resp = client_a.get(reverse("hrm:trainingfeedback_detail", args=[training_feedback_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, training_feedback_b):
        resp = client_a.get(reverse("hrm:trainingfeedback_edit", args=[training_feedback_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, training_feedback_b):
        resp = client_a.post(
            reverse("hrm:trainingfeedback_edit", args=[training_feedback_b.pk]),
            _feedback_post_data(comments="hacked"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, training_feedback_b):
        original = training_feedback_b.comments
        client_a.post(
            reverse("hrm:trainingfeedback_edit", args=[training_feedback_b.pk]),
            _feedback_post_data(comments="hacked"),
        )
        training_feedback_b.refresh_from_db()
        assert training_feedback_b.comments == original

    def test_delete_cross_tenant_404(self, client_a, training_feedback_b):
        from apps.hrm.models import TrainingFeedback
        resp = client_a.post(reverse("hrm:trainingfeedback_delete", args=[training_feedback_b.pk]))
        assert resp.status_code == 404
        assert TrainingFeedback.objects.filter(pk=training_feedback_b.pk).exists()

    def test_list_excludes_b_rows(self, client_a, training_feedback_a, training_feedback_b):
        resp = client_a.get(reverse("hrm:trainingfeedback_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_feedback_a.pk in pks
        assert training_feedback_b.pk not in pks


# ================================================================ Cross-tenant IDOR: TrainingCertificate
class TestTrainingCertificateIDOR:
    def test_detail_cross_tenant_404(self, client_a, training_certificate_b):
        resp = client_a.get(reverse("hrm:trainingcertificate_detail", args=[training_certificate_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, training_certificate_b):
        resp = client_a.get(reverse("hrm:trainingcertificate_edit", args=[training_certificate_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, training_certificate_b):
        resp = client_a.post(
            reverse("hrm:trainingcertificate_edit", args=[training_certificate_b.pk]),
            _certificate_post_data(training_certificate_b.employee, training_certificate_b.course, title="hacked"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, training_certificate_b):
        original = training_certificate_b.title
        client_a.post(
            reverse("hrm:trainingcertificate_edit", args=[training_certificate_b.pk]),
            _certificate_post_data(training_certificate_b.employee, training_certificate_b.course, title="hacked"),
        )
        training_certificate_b.refresh_from_db()
        assert training_certificate_b.title == original

    def test_delete_cross_tenant_404(self, client_a, training_certificate_b):
        from apps.hrm.models import TrainingCertificate
        training_certificate_b.status = "revoked"
        training_certificate_b.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:trainingcertificate_delete", args=[training_certificate_b.pk]))
        assert resp.status_code == 404
        assert TrainingCertificate.objects.filter(pk=training_certificate_b.pk).exists()

    def test_revoke_cross_tenant_404(self, client_a, training_certificate_b):
        resp = client_a.post(reverse("hrm:trainingcertificate_revoke", args=[training_certificate_b.pk]))
        assert resp.status_code == 404

    def test_revoke_cross_tenant_does_not_mutate_status(self, client_a, training_certificate_b):
        original = training_certificate_b.status
        client_a.post(reverse("hrm:trainingcertificate_revoke", args=[training_certificate_b.pk]))
        training_certificate_b.refresh_from_db()
        assert training_certificate_b.status == original

    def test_list_excludes_b_rows(self, client_a, training_certificate_a, training_certificate_b):
        resp = client_a.get(reverse("hrm:trainingcertificate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_certificate_a.pk in pks
        assert training_certificate_b.pk not in pks

    def test_print_cross_tenant_404(self, client_a, training_certificate_b):
        resp = client_a.get(reverse("hrm:trainingcertificate_print", args=[training_certificate_b.pk]))
        assert resp.status_code == 404

    def test_issue_from_progress_cross_tenant_pk_404(self, client_a, learning_progress_b):
        resp = client_a.post(
            reverse("hrm:trainingcertificate_issue_from_progress", args=[learning_progress_b.pk]))
        assert resp.status_code == 404

    def test_no_public_verify_endpoint(self):
        """There is no unauthenticated verify-by-code route in this pass — reversing a guessed
        'trainingcertificate_verify' url name must fail."""
        with pytest.raises(NoReverseMatch):
            reverse("hrm:trainingcertificate_verify")


# ================================================================ Feedback anonymity masking (non-admin)
class TestTrainingFeedbackAnonymityMasking:
    def test_list_masks_attendee_name_for_non_admin_viewer(self, tenant_a, employee_a2, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        c = _client_for(employee_a2.party, tenant_a, email="idor_fb_viewer@acme.com", username="idor_fb_viewer_acme")
        resp = c.get(reverse("hrm:trainingfeedback_list"))
        assert b"Alice Smith" not in resp.content

    def test_detail_masks_attendee_name_for_non_admin_viewer(self, tenant_a, employee_a2, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        c = _client_for(employee_a2.party, tenant_a, email="idor_fb_viewer2@acme.com", username="idor_fb_viewer2_acme")
        resp = c.get(reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk]))
        assert b"Alice Smith" not in resp.content

    def test_list_reveals_attendee_name_for_admin(self, client_a, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:trainingfeedback_list"))
        assert b"Alice Smith" in resp.content

    def test_detail_reveals_attendee_name_for_admin(self, client_a, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        resp = client_a.get(reverse("hrm:trainingfeedback_detail", args=[training_feedback_a.pk]))
        assert b"Alice Smith" in resp.content

    def test_non_anonymous_feedback_never_masked_for_non_admin(self, tenant_a, employee_a2, training_feedback_a):
        c = _client_for(employee_a2.party, tenant_a, email="idor_fb_viewer3@acme.com", username="idor_fb_viewer3_acme")
        resp = c.get(reverse("hrm:trainingfeedback_list"))
        assert b"Alice Smith" in resp.content


# ================================================================ Tenant is server-set, never smuggled
class TestTenantServerSet:
    def test_nomination_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, training_session_a, employee_a2):
        from apps.hrm.models import TrainingNomination
        resp = client_a.post(
            reverse("hrm:trainingnomination_create"),
            _nomination_post_data(training_session_a, employee_a2, tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        nom = TrainingNomination.objects.get(session=training_session_a, employee=employee_a2)
        assert nom.tenant_id == tenant_a.pk

    def test_attendance_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, training_session_a, employee_a2):
        from apps.hrm.models import TrainingAttendance
        resp = client_a.post(
            reverse("hrm:trainingattendance_create"),
            _attendance_post_data(training_session_a, employee_a2, tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        att = TrainingAttendance.objects.get(session=training_session_a, employee=employee_a2)
        assert att.tenant_id == tenant_a.pk

    def test_feedback_nested_create_always_server_set_tenant(self, client_a, tenant_a, tenant_b, training_attendance_a):
        """`tenant` isn't even a form field on the nested-create path — the instance is built
        server-side, so there's nothing to smuggle."""
        from apps.hrm.models import TrainingFeedback
        resp = client_a.post(
            reverse("hrm:trainingfeedback_create", args=[training_attendance_a.pk]),
            _feedback_post_data(tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        fb = TrainingFeedback.objects.get(attendance=training_attendance_a)
        assert fb.tenant_id == tenant_a.pk

    def test_certificate_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, employee_a, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        resp = client_a.post(
            reverse("hrm:trainingcertificate_create"),
            _certificate_post_data(employee_a, cert_course_a, tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        cert = TrainingCertificate.objects.get(employee=employee_a, course=cert_course_a)
        assert cert.tenant_id == tenant_a.pk

    def test_nomination_create_blocked_when_request_tenant_is_none(self, training_session_a, employee_a):
        from apps.accounts.models import User
        from apps.hrm.models import TrainingNomination
        tenantless = User.objects.create_user(
            email="notenant_nom@example.com", username="notenant_nom_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:trainingnomination_create"), _nomination_post_data(training_session_a, employee_a))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not TrainingNomination.objects.filter(session=training_session_a, employee=employee_a).exists()

    def test_attendance_create_blocked_when_request_tenant_is_none(self, training_session_a, employee_a):
        from apps.accounts.models import User
        from apps.hrm.models import TrainingAttendance
        tenantless = User.objects.create_user(
            email="notenant_att@example.com", username="notenant_att_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:trainingattendance_create"), _attendance_post_data(training_session_a, employee_a))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not TrainingAttendance.objects.filter(session=training_session_a, employee=employee_a).exists()

    def test_certificate_create_blocked_when_request_tenant_is_none(self, employee_a, cert_course_a):
        """A tenant-less (superuser-like) user is neither is_tenant_admin nor tenant-scoped — the
        @tenant_admin_required check runs first and denies with 403 before the tenant=None guard is
        ever reached."""
        from apps.accounts.models import User
        from apps.hrm.models import TrainingCertificate
        tenantless = User.objects.create_user(
            email="notenant_cert@example.com", username="notenant_cert_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:trainingcertificate_create"), _certificate_post_data(employee_a, cert_course_a))
        assert resp.status_code == 403
        assert not TrainingCertificate.objects.filter(employee=employee_a, course=cert_course_a).exists()

    def test_certificate_create_blocked_when_tenantless_but_admin_flagged(self, employee_a, cert_course_a):
        """Even a tenant-less user WITH is_tenant_admin=True (passing the decorator) must still be
        blocked by crud_create's own `request.tenant is None` guard — no orphan certificate."""
        from apps.accounts.models import User
        from apps.hrm.models import TrainingCertificate
        tenantless_admin = User.objects.create_user(
            email="notenant_cert_admin@example.com", username="notenant_cert_admin_user",
            password="TestPass123!", tenant=None, is_tenant_admin=True,
        )
        c = Client()
        c.force_login(tenantless_admin)
        resp = c.post(reverse("hrm:trainingcertificate_create"), _certificate_post_data(employee_a, cert_course_a))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not TrainingCertificate.objects.filter(employee=employee_a, course=cert_course_a).exists()


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_trainingnomination_delete_enforces_csrf(self, admin_user, nomination_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingnomination_delete", args=[nomination_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import TrainingNomination
        assert TrainingNomination.objects.filter(pk=nomination_a.pk).exists()

    def test_trainingnomination_approve_enforces_csrf(self, admin_user, nomination_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingnomination_approve", args=[nomination_a.pk]))
        assert resp.status_code == 403
        nomination_a.refresh_from_db()
        assert nomination_a.status == "pending"

    def test_trainingattendance_delete_enforces_csrf(self, admin_user, tenant_a, training_session_a, employee_a2):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance.objects.create(tenant=tenant_a, session=training_session_a, employee=employee_a2)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingattendance_delete", args=[att.pk]))
        assert resp.status_code == 403
        assert TrainingAttendance.objects.filter(pk=att.pk).exists()

    def test_trainingfeedback_delete_enforces_csrf(self, admin_user, training_feedback_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingfeedback_delete", args=[training_feedback_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import TrainingFeedback
        assert TrainingFeedback.objects.filter(pk=training_feedback_a.pk).exists()

    def test_trainingcertificate_revoke_enforces_csrf(self, admin_user, training_certificate_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingcertificate_revoke", args=[training_certificate_a.pk]))
        assert resp.status_code == 403
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.status == "issued"

    def test_trainingnomination_create_enforces_csrf(self, admin_user, tenant_a, training_session_a, employee_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:trainingnomination_create"), _nomination_post_data(training_session_a, employee_a))
        assert resp.status_code == 403
        from apps.hrm.models import TrainingNomination
        assert not TrainingNomination.objects.filter(tenant=tenant_a, session=training_session_a, employee=employee_a).exists()
