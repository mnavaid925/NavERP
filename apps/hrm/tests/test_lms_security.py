"""Security tests for HRM 3.23 Learning Management (LMS): anonymous redirect-to-login, cross-tenant
IDOR (404) on LearningContentItem/LearningPath/LearningPathItem/LearningProgress detail/edit/delete (+
list isolation), nested-create with a cross-tenant parent pk (course_pk / path_pk) -> 404, tenant is
always server-set (never smuggled via POST data, and blocked outright when request.tenant is None), and
CSRF enforcement on the POST-only delete/create actions. LMS is ordinary tenant-scoped CRUD — no
confidentiality gate — mirrors test_training_security.py conventions; client_a is the tenant admin."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _content_item_post_data(**overrides):
    data = {
        "title": "Hacked Lesson", "description": "", "content_type": "text", "sequence": "1",
        "is_required": "on", "estimated_duration_minutes": "", "video_url": "",
        "external_url": "", "body_text": "Some article content.",
        "pass_threshold_percent": "70", "max_attempts": "1", "time_limit_minutes": "",
    }
    data.update(overrides)
    return data


def _path_post_data(**overrides):
    data = {
        "title": "Security Test Path", "description": "", "target_designation": "",
        "target_department": "", "is_mandatory": "", "is_active": "on",
    }
    data.update(overrides)
    return data


def _path_item_post_data(course, **overrides):
    data = {"course": course.pk, "sequence": "1", "is_mandatory": "on"}
    data.update(overrides)
    return data


def _progress_post_data(employee, course, **overrides):
    data = {
        "employee": employee.pk, "course": course.pk, "learning_path": "",
        "status": "not_started", "percent_complete": "0", "time_spent_minutes": "0",
        "score": "", "passed": "", "attempt_count": "0", "points_earned": "0",
        "started_at": "", "completed_at": "",
    }
    data.update(overrides)
    return data


# ================================================================ Anonymous -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name", [
        "hrm:learningcontentitem_list", "hrm:learningpath_list", "hrm:learningpath_create",
        "hrm:learningpathitem_list", "hrm:learningprogress_list", "hrm:learningprogress_create",
        "hrm:learning_leaderboard", "hrm:learning_team_progress",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_and_edit_pages(
        self, client, content_item_a, learning_path_a, path_item_a, learning_progress_a
    ):
        for url_name, pk in [
            ("hrm:learningcontentitem_detail", content_item_a.pk),
            ("hrm:learningcontentitem_edit", content_item_a.pk),
            ("hrm:learningpath_detail", learning_path_a.pk),
            ("hrm:learningpath_edit", learning_path_a.pk),
            ("hrm:learningpathitem_detail", path_item_a.pk),
            ("hrm:learningpathitem_edit", path_item_a.pk),
            ("hrm:learningprogress_detail", learning_progress_a.pk),
            ("hrm:learningprogress_edit", learning_progress_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_delete(
        self, client, content_item_a, learning_path_a, path_item_a, learning_progress_a
    ):
        for url_name, pk in [
            ("hrm:learningcontentitem_delete", content_item_a.pk),
            ("hrm:learningpath_delete", learning_path_a.pk),
            ("hrm:learningpathitem_delete", path_item_a.pk),
            ("hrm:learningprogress_delete", learning_progress_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_redirected_on_nested_create(self, client, training_course_a, learning_path_a):
        for url_name, pk in [
            ("hrm:learningcontentitem_create", training_course_a.pk),
            ("hrm:learningpathitem_create", learning_path_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ Cross-tenant IDOR
class TestLearningContentItemIDOR:
    def test_detail_cross_tenant_404(self, client_a, content_item_b):
        resp = client_a.get(reverse("hrm:learningcontentitem_detail", args=[content_item_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, content_item_b):
        resp = client_a.get(reverse("hrm:learningcontentitem_edit", args=[content_item_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, content_item_b):
        resp = client_a.post(
            reverse("hrm:learningcontentitem_edit", args=[content_item_b.pk]),
            _content_item_post_data(title="hacked"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, content_item_b):
        original_title = content_item_b.title
        client_a.post(
            reverse("hrm:learningcontentitem_edit", args=[content_item_b.pk]),
            _content_item_post_data(title="hacked"),
        )
        content_item_b.refresh_from_db()
        assert content_item_b.title == original_title

    def test_delete_cross_tenant_404(self, client_a, content_item_b):
        from apps.hrm.models import LearningContentItem
        resp = client_a.post(reverse("hrm:learningcontentitem_delete", args=[content_item_b.pk]))
        assert resp.status_code == 404
        assert LearningContentItem.objects.filter(pk=content_item_b.pk).exists()

    def test_list_excludes_b_items(self, client_a, content_item_a, content_item_b):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert content_item_a.pk in pks
        assert content_item_b.pk not in pks

    def test_nested_create_cross_tenant_course_pk_404(self, client_a, training_course_b):
        resp = client_a.get(reverse("hrm:learningcontentitem_create", args=[training_course_b.pk]))
        assert resp.status_code == 404

    def test_nested_create_post_cross_tenant_course_pk_404(self, client_a, tenant_a, training_course_b):
        from apps.hrm.models import LearningContentItem
        resp = client_a.post(
            reverse("hrm:learningcontentitem_create", args=[training_course_b.pk]),
            _content_item_post_data(),
        )
        assert resp.status_code == 404
        assert not LearningContentItem.objects.filter(tenant=tenant_a, title="Hacked Lesson").exists()


class TestLearningPathIDOR:
    def test_detail_cross_tenant_404(self, client_a, learning_path_b):
        resp = client_a.get(reverse("hrm:learningpath_detail", args=[learning_path_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, learning_path_b):
        resp = client_a.get(reverse("hrm:learningpath_edit", args=[learning_path_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, learning_path_b):
        resp = client_a.post(
            reverse("hrm:learningpath_edit", args=[learning_path_b.pk]),
            _path_post_data(title="hacked"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, learning_path_b):
        original_title = learning_path_b.title
        client_a.post(
            reverse("hrm:learningpath_edit", args=[learning_path_b.pk]),
            _path_post_data(title="hacked"),
        )
        learning_path_b.refresh_from_db()
        assert learning_path_b.title == original_title

    def test_delete_cross_tenant_404(self, client_a, learning_path_b):
        from apps.hrm.models import LearningPath
        resp = client_a.post(reverse("hrm:learningpath_delete", args=[learning_path_b.pk]))
        assert resp.status_code == 404
        assert LearningPath.objects.filter(pk=learning_path_b.pk).exists()

    def test_list_excludes_b_paths(self, client_a, learning_path_a, learning_path_b):
        resp = client_a.get(reverse("hrm:learningpath_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_path_a.pk in pks
        assert learning_path_b.pk not in pks

    def test_nested_item_create_cross_tenant_path_pk_404(self, client_a, learning_path_b):
        resp = client_a.get(reverse("hrm:learningpathitem_create", args=[learning_path_b.pk]))
        assert resp.status_code == 404

    def test_nested_item_create_post_cross_tenant_path_pk_404(self, client_a, tenant_a, learning_path_b, training_course_a):
        from apps.hrm.models import LearningPathItem
        resp = client_a.post(
            reverse("hrm:learningpathitem_create", args=[learning_path_b.pk]),
            _path_item_post_data(training_course_a),
        )
        assert resp.status_code == 404
        assert not LearningPathItem.objects.filter(tenant=tenant_a, path_id=learning_path_b.pk).exists()


class TestLearningPathItemIDOR:
    def test_detail_cross_tenant_404(self, client_a, path_item_b):
        resp = client_a.get(reverse("hrm:learningpathitem_detail", args=[path_item_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, path_item_b):
        resp = client_a.get(reverse("hrm:learningpathitem_edit", args=[path_item_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, path_item_b, training_course_b):
        resp = client_a.post(
            reverse("hrm:learningpathitem_edit", args=[path_item_b.pk]),
            _path_item_post_data(training_course_b, sequence="9"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, path_item_b, training_course_b):
        original_sequence = path_item_b.sequence
        client_a.post(
            reverse("hrm:learningpathitem_edit", args=[path_item_b.pk]),
            _path_item_post_data(training_course_b, sequence="99"),
        )
        path_item_b.refresh_from_db()
        assert path_item_b.sequence == original_sequence

    def test_delete_cross_tenant_404(self, client_a, path_item_b):
        from apps.hrm.models import LearningPathItem
        resp = client_a.post(reverse("hrm:learningpathitem_delete", args=[path_item_b.pk]))
        assert resp.status_code == 404
        assert LearningPathItem.objects.filter(pk=path_item_b.pk).exists()

    def test_list_excludes_b_items(self, client_a, path_item_a, path_item_b):
        resp = client_a.get(reverse("hrm:learningpathitem_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert path_item_a.pk in pks
        assert path_item_b.pk not in pks


class TestLearningProgressIDOR:
    def test_detail_cross_tenant_404(self, client_a, learning_progress_b):
        resp = client_a.get(reverse("hrm:learningprogress_detail", args=[learning_progress_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, learning_progress_b):
        resp = client_a.get(reverse("hrm:learningprogress_edit", args=[learning_progress_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, learning_progress_b, employee_b, training_course_b):
        resp = client_a.post(
            reverse("hrm:learningprogress_edit", args=[learning_progress_b.pk]),
            _progress_post_data(employee_b, training_course_b, status="completed"),
        )
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, learning_progress_b, employee_b, training_course_b):
        original_status = learning_progress_b.status
        client_a.post(
            reverse("hrm:learningprogress_edit", args=[learning_progress_b.pk]),
            _progress_post_data(employee_b, training_course_b, status="completed"),
        )
        learning_progress_b.refresh_from_db()
        assert learning_progress_b.status == original_status

    def test_delete_cross_tenant_404(self, client_a, learning_progress_b):
        from apps.hrm.models import LearningProgress
        resp = client_a.post(reverse("hrm:learningprogress_delete", args=[learning_progress_b.pk]))
        assert resp.status_code == 404
        assert LearningProgress.objects.filter(pk=learning_progress_b.pk).exists()

    def test_list_excludes_b_rows(self, client_a, learning_progress_a, learning_progress_b):
        resp = client_a.get(reverse("hrm:learningprogress_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_progress_a.pk in pks
        assert learning_progress_b.pk not in pks

    def test_create_nested_cross_tenant_employee_ignored_by_scoped_queryset(self, client_a, employee_b, training_course_a):
        """employee is a ModelChoiceField auto-scoped to request.tenant by TenantModelForm — a
        cross-tenant employee pk in the POST body fails form validation (not a silent cross-tenant
        write)."""
        from apps.hrm.models import LearningProgress
        resp = client_a.post(
            reverse("hrm:learningprogress_create"),
            _progress_post_data(employee_b, training_course_a),
        )
        assert resp.status_code == 200  # form re-rendered with a validation error
        assert not LearningProgress.objects.filter(course=training_course_a).exists()


# ================================================================ Tenant is server-set, never smuggled
class TestTenantServerSet:
    def test_learningpath_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b):
        from apps.hrm.models import LearningPath
        resp = client_a.post(
            reverse("hrm:learningpath_create"),
            _path_post_data(title="Smuggle Test Path", tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        path = LearningPath.objects.get(title="Smuggle Test Path")
        assert path.tenant_id == tenant_a.pk

    def test_learningprogress_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, employee_a, training_course_a):
        from apps.hrm.models import LearningProgress
        resp = client_a.post(
            reverse("hrm:learningprogress_create"),
            _progress_post_data(employee_a, training_course_a, tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        progress = LearningProgress.objects.get(employee=employee_a, course=training_course_a)
        assert progress.tenant_id == tenant_a.pk

    def test_learningcontentitem_nested_create_always_server_set_tenant(self, client_a, tenant_a, tenant_b, training_course_a):
        """`tenant` isn't even a form field on the nested-create path — the instance is built server-side
        as `LearningContentItem(tenant=request.tenant, course=course)`, so there's nothing to smuggle."""
        from apps.hrm.models import LearningContentItem
        resp = client_a.post(
            reverse("hrm:learningcontentitem_create", args=[training_course_a.pk]),
            _content_item_post_data(title="Smuggle Test Content", tenant=tenant_b.pk),
        )
        assert resp.status_code == 302
        item = LearningContentItem.objects.get(title="Smuggle Test Content")
        assert item.tenant_id == tenant_a.pk

    def test_learningpath_create_blocked_when_request_tenant_is_none(self):
        from apps.accounts.models import User
        from apps.hrm.models import LearningPath
        tenantless = User.objects.create_user(
            email="notenant_lms@example.com", username="notenant_lms_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:learningpath_create"), _path_post_data(title="Orphan Path"))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not LearningPath.objects.filter(title="Orphan Path").exists()

    def test_learningprogress_create_blocked_when_request_tenant_is_none(self, employee_a, training_course_a):
        from apps.accounts.models import User
        from apps.hrm.models import LearningProgress
        tenantless = User.objects.create_user(
            email="notenant_lms2@example.com", username="notenant_lms_user2", password="TestPass123!",
            tenant=None, is_tenant_admin=False,
        )
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:learningprogress_create"), _progress_post_data(employee_a, training_course_a))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not LearningProgress.objects.exists()


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_learningcontentitem_delete_enforces_csrf(self, admin_user, content_item_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:learningcontentitem_delete", args=[content_item_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import LearningContentItem
        assert LearningContentItem.objects.filter(pk=content_item_a.pk).exists()

    def test_learningpath_delete_enforces_csrf(self, admin_user, learning_path_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:learningpath_delete", args=[learning_path_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import LearningPath
        assert LearningPath.objects.filter(pk=learning_path_a.pk).exists()

    def test_learningpathitem_delete_enforces_csrf(self, admin_user, path_item_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:learningpathitem_delete", args=[path_item_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import LearningPathItem
        assert LearningPathItem.objects.filter(pk=path_item_a.pk).exists()

    def test_learningprogress_delete_enforces_csrf(self, admin_user, learning_progress_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:learningprogress_delete", args=[learning_progress_a.pk]))
        assert resp.status_code == 403
        from apps.hrm.models import LearningProgress
        assert LearningProgress.objects.filter(pk=learning_progress_a.pk).exists()

    def test_learningpath_create_enforces_csrf(self, admin_user, tenant_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:learningpath_create"), _path_post_data(title="CSRF Bypass Attempt"))
        assert resp.status_code == 403
        from apps.hrm.models import LearningPath
        assert not LearningPath.objects.filter(tenant=tenant_a, title="CSRF Bypass Attempt").exists()
