"""Security tests for HRM 3.22 Training Management: anonymous redirect-to-login, cross-tenant IDOR
(404) on TrainingCourse/TrainingSession detail/edit/delete (+ list isolation), tenant-server-set
(never smuggled via POST data, and creation is blocked outright when request.tenant is None), and
CSRF enforcement on the POST-only delete actions. Training is ordinary tenant-scoped CRUD — no
confidentiality gate — mirrors test_org_structure.py / test_goals_security.py conventions for a
non-confidential sub-module."""
import datetime

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h, mi):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


def _course_post_data(**overrides):
    data = {
        "title": "Security Test Course", "description": "", "category": "technical",
        "delivery_mode": "classroom", "provider_type": "internal", "duration_hours": "1",
        "is_certification": "", "certification_name": "", "certification_validity_months": "",
        "prerequisite_course": "", "default_capacity": "", "is_active": "on",
    }
    data.update(overrides)
    return data


def _session_post_data(course, **overrides):
    data = {
        "course": course.pk, "delivery_mode": "classroom", "status": "scheduled",
        "start_datetime": "2026-08-01T09:00", "end_datetime": "2026-08-01T17:00",
        "timezone": "UTC", "capacity": "10", "venue_name": "Security Test Room",
        "venue_address": "", "meeting_platform": "", "meeting_link": "", "meeting_id": "",
        "instructor_employee": "", "external_instructor_name": "", "external_vendor": "",
        "estimated_cost": "", "actual_cost": "", "currency": "", "invoice_reference": "", "notes": "",
    }
    data.update(overrides)
    return data


# ================================================================ Anonymous -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name", [
        "hrm:trainingcourse_list", "hrm:trainingcourse_create",
        "hrm:trainingsession_list", "hrm:trainingsession_create",
        "hrm:training_calendar",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_and_edit_pages(self, client, training_course_a, training_session_a):
        for url_name, pk in [
            ("hrm:trainingcourse_detail", training_course_a.pk),
            ("hrm:trainingcourse_edit", training_course_a.pk),
            ("hrm:trainingsession_detail", training_session_a.pk),
            ("hrm:trainingsession_edit", training_session_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_delete(self, client, training_course_a, training_session_a):
        for url_name, pk in [
            ("hrm:trainingcourse_delete", training_course_a.pk),
            ("hrm:trainingsession_delete", training_session_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ Cross-tenant IDOR
class TestTrainingCourseIDOR:
    def test_detail_cross_tenant_404(self, client_a, training_course_b):
        resp = client_a.get(reverse("hrm:trainingcourse_detail", args=[training_course_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, training_course_b):
        resp = client_a.get(reverse("hrm:trainingcourse_edit", args=[training_course_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, training_course_b):
        resp = client_a.post(
            reverse("hrm:trainingcourse_edit", args=[training_course_b.pk]),
            _course_post_data(title="hacked"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, training_course_b):
        original_title = training_course_b.title
        client_a.post(
            reverse("hrm:trainingcourse_edit", args=[training_course_b.pk]),
            _course_post_data(title="hacked"),
        )
        training_course_b.refresh_from_db()
        assert training_course_b.title == original_title

    def test_delete_cross_tenant_404(self, client_a, training_course_b):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_delete", args=[training_course_b.pk]))
        assert resp.status_code == 404
        assert TrainingCourse.objects.filter(pk=training_course_b.pk).exists()

    def test_list_excludes_b_courses(self, client_a, training_course_a, training_course_b):
        resp = client_a.get(reverse("hrm:trainingcourse_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks
        assert training_course_b.pk not in pks


class TestTrainingSessionIDOR:
    def test_detail_cross_tenant_404(self, client_a, training_session_b):
        resp = client_a.get(reverse("hrm:trainingsession_detail", args=[training_session_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, training_session_b):
        resp = client_a.get(reverse("hrm:trainingsession_edit", args=[training_session_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, training_session_b):
        resp = client_a.post(
            reverse("hrm:trainingsession_edit", args=[training_session_b.pk]),
            _session_post_data(training_session_b.course, venue_name="hacked"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, training_session_b):
        original_venue = training_session_b.venue_name
        client_a.post(
            reverse("hrm:trainingsession_edit", args=[training_session_b.pk]),
            _session_post_data(training_session_b.course, venue_name="hacked"),
        )
        training_session_b.refresh_from_db()
        assert training_session_b.venue_name == original_venue

    def test_delete_cross_tenant_404(self, client_a, training_session_b):
        from apps.hrm.models import TrainingSession
        resp = client_a.post(reverse("hrm:trainingsession_delete", args=[training_session_b.pk]))
        assert resp.status_code == 404
        assert TrainingSession.objects.filter(pk=training_session_b.pk).exists()

    def test_list_excludes_b_sessions(self, client_a, training_session_a, training_session_b):
        resp = client_a.get(reverse("hrm:trainingsession_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks
        assert training_session_b.pk not in pks

    def test_create_nested_cross_tenant_course_ignored_by_scoped_queryset(
        self, client_a, training_course_b
    ):
        """course is a ModelChoiceField auto-scoped to request.tenant by TenantModelForm — a
        cross-tenant course pk in the POST body fails form validation (not a silent cross-tenant
        write)."""
        from apps.hrm.models import TrainingSession
        resp = client_a.post(
            reverse("hrm:trainingsession_create"),
            _session_post_data(training_course_b),
        )
        assert resp.status_code == 200  # form re-rendered with a validation error
        assert not TrainingSession.objects.filter(venue_name="Security Test Room").exists()


# ================================================================ Tenant is server-set, never smuggled
class TestTenantServerSet:
    def test_course_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(
            reverse("hrm:trainingcourse_create"),
            _course_post_data(title="Smuggle Test Course", tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        course = TrainingCourse.objects.get(title="Smuggle Test Course")
        assert course.tenant_id == tenant_a.pk

    def test_session_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, training_course_a):
        from apps.hrm.models import TrainingSession
        resp = client_a.post(
            reverse("hrm:trainingsession_create"),
            _session_post_data(training_course_a, venue_name="Smuggle Room", tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        session = TrainingSession.objects.get(venue_name="Smuggle Room")
        assert session.tenant_id == tenant_a.pk

    def test_course_create_blocked_when_request_tenant_is_none(self):
        from apps.accounts.models import User
        from apps.hrm.models import TrainingCourse
        tenantless = User.objects.create_user(
            email="notenant@example.com", username="notenant_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:trainingcourse_create"), _course_post_data(title="Orphan Course"))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not TrainingCourse.objects.filter(title="Orphan Course").exists()

    def test_session_create_blocked_when_request_tenant_is_none(self, tenant_a, training_course_a):
        from apps.accounts.models import User
        from apps.hrm.models import TrainingSession
        tenantless = User.objects.create_user(
            email="notenant2@example.com", username="notenant_user2", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(
            reverse("hrm:trainingsession_create"),
            _session_post_data(training_course_a, venue_name="Orphan Room"),
        )
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not TrainingSession.objects.filter(venue_name="Orphan Room").exists()


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_trainingcourse_delete_enforces_csrf(self, admin_user, training_course_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingcourse_delete", args=[training_course_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import TrainingCourse
        assert TrainingCourse.objects.filter(pk=training_course_a.pk).exists()

    def test_trainingsession_delete_enforces_csrf(self, admin_user, training_session_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingsession_delete", args=[training_session_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import TrainingSession
        assert TrainingSession.objects.filter(pk=training_session_a.pk).exists()

    def test_trainingcourse_create_enforces_csrf(self, admin_user, tenant_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:trainingcourse_create"), _course_post_data(title="CSRF Bypass Attempt"))
        assert resp.status_code == 403
        from apps.hrm.models import TrainingCourse
        assert not TrainingCourse.objects.filter(tenant=tenant_a, title="CSRF Bypass Attempt").exists()
