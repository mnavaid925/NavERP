"""Tests for HRM 3.23 Learning Management (LMS) views: LearningContentItem CRUD (nested create under a
TrainingCourse), LearningPath CRUD, LearningPathItem CRUD (nested create under a LearningPath), and
LearningProgress CRUD, plus the computed gamification leaderboard + manager team-progress rollup. Also
covers the trainingcourse_detail cross-touch (course detail lists its LMS content items) and the
TrainingCourse delete ProtectedError guard now that LearningPathItem/LearningProgress ALSO reference a
course (3.22's guard only covered TrainingSession). LMS is ordinary tenant-scoped CRUD — no
confidentiality gate — mirrors test_training_views.py conventions; client_a is the tenant admin."""
import datetime

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h=0, mi=0):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


def _content_item_post_data(**overrides):
    data = {
        "title": "New Lesson", "description": "", "content_type": "text", "sequence": "1",
        "is_required": "on", "estimated_duration_minutes": "", "video_url": "",
        "external_url": "", "body_text": "Some article content.",
        "pass_threshold_percent": "70", "max_attempts": "1", "time_limit_minutes": "",
    }
    data.update(overrides)
    return data


def _path_post_data(**overrides):
    data = {
        "title": "New Learning Path", "description": "", "target_designation": "",
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


# ================================================================ LearningContentItem CRUD
class TestLearningContentItemListView:
    def test_list_200(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert content_item_a.pk in pks

    def test_list_filter_by_content_type_assessment_returns_only_assessment(
        self, client_a, tenant_a, training_course_a, content_item_a
    ):
        from apps.hrm.models import LearningContentItem
        quiz = LearningContentItem.objects.create(
            tenant=tenant_a, course=training_course_a, title="Quiz", content_type="assessment", sequence=2,
        )
        resp = client_a.get(reverse("hrm:learningcontentitem_list"), {"content_type": "assessment"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert quiz.pk in pks
        assert content_item_a.pk not in pks  # content_item_a is "video"

    def test_list_filter_by_course(self, client_a, training_course_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"), {"course": training_course_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert content_item_a.pk in pks

    def test_list_filter_by_is_required(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"), {"is_required": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert content_item_a.pk in pks

    def test_list_has_choices_context(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"))
        assert "content_type_choices" in resp.context
        assert "courses" in resp.context

    def test_bad_course_filter_does_not_500(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"), {"course": "abc"})
        assert resp.status_code == 200

    def test_bad_is_required_filter_does_not_500(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"), {"is_required": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, content_item_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:learningcontentitem_list"))


class TestLearningContentItemNestedCreateView:
    def test_get_200(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_create", args=[training_course_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_on_course_and_redirects_to_course_detail(self, client_a, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        resp = client_a.post(
            reverse("hrm:learningcontentitem_create", args=[training_course_a.pk]),
            _content_item_post_data(title="Welcome Article"),
        )
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingcourse_detail", args=[training_course_a.pk])
        item = LearningContentItem.objects.filter(tenant=tenant_a, title="Welcome Article").first()
        assert item is not None
        assert item.course_id == training_course_a.pk
        assert item.tenant_id == tenant_a.pk

    def test_post_video_without_url_rejected(self, client_a, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        resp = client_a.post(
            reverse("hrm:learningcontentitem_create", args=[training_course_a.pk]),
            _content_item_post_data(title="Broken Video", content_type="video", body_text="", video_url=""),
        )
        assert resp.status_code == 200
        assert not LearningContentItem.objects.filter(tenant=tenant_a, title="Broken Video").exists()

    def test_form_has_no_tenant_course_or_id_field(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_create", args=[training_course_a.pk]))
        fields = resp.context["form"].fields
        assert "tenant" not in fields
        assert "course" not in fields


class TestLearningContentItemDetailEditDelete:
    def test_detail_200(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_detail", args=[content_item_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_detail", args=[content_item_a.pk]))
        assert resp.context["obj"].pk == content_item_a.pk

    def test_edit_get_200(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_edit", args=[content_item_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_title(self, client_a, content_item_a):
        resp = client_a.post(
            reverse("hrm:learningcontentitem_edit", args=[content_item_a.pk]),
            _content_item_post_data(title="Updated Title", content_type="video",
                                     video_url="https://example.com/updated.mp4", body_text=""),
        )
        assert resp.status_code == 302
        content_item_a.refresh_from_db()
        assert content_item_a.title == "Updated Title"

    def test_delete_post_removes(self, client_a, content_item_a):
        from apps.hrm.models import LearningContentItem
        pk = content_item_a.pk
        resp = client_a.post(reverse("hrm:learningcontentitem_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LearningContentItem.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, content_item_a):
        resp = client_a.get(reverse("hrm:learningcontentitem_delete", args=[content_item_a.pk]))
        assert resp.status_code == 405


# ================================================================ LearningPath CRUD
class TestLearningPathListView:
    def test_list_200(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_path_a.pk in pks

    def test_list_filter_by_is_mandatory(self, client_a, tenant_a):
        from apps.hrm.models import LearningPath
        mandatory = LearningPath.objects.create(tenant=tenant_a, title="Compliance 101", is_mandatory=True)
        resp = client_a.get(reverse("hrm:learningpath_list"), {"is_mandatory": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert mandatory.pk in pks

    def test_list_search_by_title(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_list"), {"q": "Engineering Onboarding"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_path_a.pk in pks

    def test_list_search_by_number(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_list"), {"q": learning_path_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_path_a.pk in pks

    def test_bad_target_designation_filter_does_not_500(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_list"), {"target_designation": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, learning_path_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:learningpath_list"))


class TestLearningPathCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:learningpath_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import LearningPath
        resp = client_a.post(reverse("hrm:learningpath_create"), _path_post_data())
        assert resp.status_code == 302
        path = LearningPath.objects.filter(tenant=tenant_a, title="New Learning Path").first()
        assert path is not None
        assert path.tenant_id == tenant_a.pk
        assert path.number.startswith("LNP-")

    def test_form_has_no_tenant_or_number_field(self, client_a):
        resp = client_a.get(reverse("hrm:learningpath_create"))
        fields = resp.context["form"].fields
        assert "tenant" not in fields
        assert "number" not in fields


class TestLearningPathDetailEditDelete:
    def test_detail_200(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_detail", args=[learning_path_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_detail", args=[learning_path_a.pk]))
        assert "obj" in resp.context
        assert "items" in resp.context

    def test_detail_lists_items(self, client_a, learning_path_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpath_detail", args=[learning_path_a.pk]))
        pks = [i.pk for i in resp.context["items"]]
        assert path_item_a.pk in pks

    def test_edit_get_200(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_edit", args=[learning_path_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_title(self, client_a, learning_path_a):
        resp = client_a.post(
            reverse("hrm:learningpath_edit", args=[learning_path_a.pk]),
            _path_post_data(title="Engineering Onboarding (Updated)"),
        )
        assert resp.status_code == 302
        learning_path_a.refresh_from_db()
        assert learning_path_a.title == "Engineering Onboarding (Updated)"

    def test_delete_post_removes(self, client_a, tenant_a):
        from apps.hrm.models import LearningPath
        path = LearningPath.objects.create(tenant=tenant_a, title="Deletable Path")
        resp = client_a.post(reverse("hrm:learningpath_delete", args=[path.pk]))
        assert resp.status_code == 302
        assert not LearningPath.objects.filter(pk=path.pk).exists()

    def test_delete_cascades_items(self, client_a, learning_path_a, path_item_a):
        from apps.hrm.models import LearningPathItem
        resp = client_a.post(reverse("hrm:learningpath_delete", args=[learning_path_a.pk]))
        assert resp.status_code == 302
        assert not LearningPathItem.objects.filter(pk=path_item_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpath_delete", args=[learning_path_a.pk]))
        assert resp.status_code == 405


# ================================================================ LearningPathItem CRUD (nested under a path)
class TestLearningPathItemListView:
    def test_list_200(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert path_item_a.pk in pks

    def test_list_filter_by_path(self, client_a, learning_path_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_list"), {"path": learning_path_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert path_item_a.pk in pks

    def test_list_filter_by_course(self, client_a, training_course_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_list"), {"course": training_course_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert path_item_a.pk in pks

    def test_bad_path_filter_does_not_500(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_list"), {"path": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_list"), {"page": "999"})
        assert resp.status_code == 200


class TestLearningPathItemNestedCreateView:
    def test_get_200(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpathitem_create", args=[learning_path_a.pk]))
        assert resp.status_code == 200

    def test_post_creates_on_path_and_redirects_to_path_detail(self, client_a, tenant_a, learning_path_a, training_course_a):
        from apps.hrm.models import LearningPathItem
        resp = client_a.post(
            reverse("hrm:learningpathitem_create", args=[learning_path_a.pk]),
            _path_item_post_data(training_course_a),
        )
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:learningpath_detail", args=[learning_path_a.pk])
        item = LearningPathItem.objects.filter(tenant=tenant_a, path=learning_path_a, course=training_course_a).first()
        assert item is not None
        assert item.tenant_id == tenant_a.pk

    def test_post_duplicate_course_rejected(self, client_a, learning_path_a, training_course_a, path_item_a):
        from apps.hrm.models import LearningPathItem
        resp = client_a.post(
            reverse("hrm:learningpathitem_create", args=[learning_path_a.pk]),
            _path_item_post_data(training_course_a, sequence="2"),
        )
        assert resp.status_code == 200
        assert LearningPathItem.objects.filter(tenant=learning_path_a.tenant, path=learning_path_a).count() == 1

    def test_form_has_no_tenant_or_path_field(self, client_a, learning_path_a):
        resp = client_a.get(reverse("hrm:learningpathitem_create", args=[learning_path_a.pk]))
        fields = resp.context["form"].fields
        assert "tenant" not in fields
        assert "path" not in fields


class TestLearningPathItemDetailEditDelete:
    def test_detail_200(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_detail", args=[path_item_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_edit", args=[path_item_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_sequence(self, client_a, path_item_a, training_course_a):
        resp = client_a.post(
            reverse("hrm:learningpathitem_edit", args=[path_item_a.pk]),
            _path_item_post_data(training_course_a, sequence="9"),
        )
        assert resp.status_code == 302
        path_item_a.refresh_from_db()
        assert path_item_a.sequence == 9

    def test_delete_post_removes_and_redirects_to_path_detail(self, client_a, learning_path_a, path_item_a):
        from apps.hrm.models import LearningPathItem
        pk = path_item_a.pk
        resp = client_a.post(reverse("hrm:learningpathitem_delete", args=[pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:learningpath_detail", args=[learning_path_a.pk])
        assert not LearningPathItem.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, path_item_a):
        resp = client_a.get(reverse("hrm:learningpathitem_delete", args=[path_item_a.pk]))
        assert resp.status_code == 405


# ================================================================ LearningProgress CRUD
class TestLearningProgressListView:
    def test_list_200(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_progress_a.pk in pks

    def test_list_filter_by_status_completed_returns_only_completed(
        self, client_a, tenant_a, employee_a2, training_course_a, learning_progress_a
    ):
        from apps.hrm.models import LearningProgress
        completed = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a2, course=training_course_a, status="completed",
        )
        resp = client_a.get(reverse("hrm:learningprogress_list"), {"status": "completed"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert completed.pk in pks
        assert learning_progress_a.pk not in pks  # learning_progress_a is not_started

    def test_list_filter_by_employee(self, client_a, employee_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"), {"employee": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_progress_a.pk in pks

    def test_list_filter_by_course(self, client_a, training_course_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"), {"course": training_course_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert learning_progress_a.pk in pks

    def test_list_has_choices_context(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"))
        assert "status_choices" in resp.context
        assert "courses" in resp.context
        assert "employees" in resp.context
        assert "paths" in resp.context

    def test_bad_course_filter_does_not_500(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"), {"course": "abc"})
        assert resp.status_code == 200

    def test_bad_status_filter_does_not_500(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"), {"status": "not-a-status"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, learning_progress_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:learningprogress_list"))


class TestLearningProgressCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:learningprogress_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import LearningProgress
        resp = client_a.post(
            reverse("hrm:learningprogress_create"), _progress_post_data(employee_a, training_course_a),
        )
        assert resp.status_code == 302
        progress = LearningProgress.objects.filter(tenant=tenant_a, employee=employee_a, course=training_course_a).first()
        assert progress is not None
        assert progress.tenant_id == tenant_a.pk

    def test_post_duplicate_employee_course_rejected(self, client_a, employee_a, training_course_a, learning_progress_a):
        resp = client_a.post(
            reverse("hrm:learningprogress_create"), _progress_post_data(employee_a, training_course_a),
        )
        assert resp.status_code == 200
        assert "form" in resp.context
        assert not resp.context["form"].is_valid()

    def test_form_has_no_tenant_field(self, client_a):
        resp = client_a.get(reverse("hrm:learningprogress_create"))
        fields = resp.context["form"].fields
        assert "tenant" not in fields


class TestLearningProgressDetailEditDelete:
    def test_detail_200(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_detail", args=[learning_progress_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_edit", args=[learning_progress_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_status(self, client_a, learning_progress_a, employee_a, training_course_a):
        resp = client_a.post(
            reverse("hrm:learningprogress_edit", args=[learning_progress_a.pk]),
            _progress_post_data(employee_a, training_course_a, status="in_progress", percent_complete="40"),
        )
        assert resp.status_code == 302
        learning_progress_a.refresh_from_db()
        assert learning_progress_a.status == "in_progress"
        assert learning_progress_a.percent_complete == 40

    def test_delete_post_removes(self, client_a, learning_progress_a):
        from apps.hrm.models import LearningProgress
        pk = learning_progress_a.pk
        resp = client_a.post(reverse("hrm:learningprogress_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LearningProgress.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learningprogress_delete", args=[learning_progress_a.pk]))
        assert resp.status_code == 405


# ================================================================ Gamification leaderboard
class TestLearningLeaderboard:
    def test_renders_200(self, client_a, learning_progress_a):
        resp = client_a.get(reverse("hrm:learning_leaderboard"))
        assert resp.status_code == 200

    def test_ranks_by_points_descending_and_shows_level(self, client_a, tenant_a, employee_a, employee_a2, training_course_a):
        from apps.hrm.models import LearningProgress, TrainingCourse
        LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=training_course_a, points_earned=50)
        other_course = TrainingCourse.objects.create(tenant=tenant_a, title="Other Course")
        LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a2, course=other_course, points_earned=500)
        resp = client_a.get(reverse("hrm:learning_leaderboard"))
        rows = resp.context["leaderboard_rows"]
        # Highest total_points ranked first.
        assert rows[0]["employee_id"] == employee_a2.pk
        assert rows[0]["rank"] == 1
        assert rows[0]["level"] == "Gold"  # 500 points -> Gold tier (>=400)
        assert rows[0]["total_points"] == 500
        low_row = next(r for r in rows if r["employee_id"] == employee_a.pk)
        assert low_row["total_points"] == 50
        assert low_row["level"] == "Bronze"


# ================================================================ Manager team-progress rollup
class TestLearningTeamProgress:
    def test_200_for_manager_linked_user(self, tenant_a, employment_a, person_a2, employee_a2, learning_progress_a):
        from apps.accounts.models import User
        from django.test import Client
        employment_a.manager = person_a2
        employment_a.save(update_fields=["manager"])
        manager_user = User.objects.create_user(
            email="manager_lms@acme.com", username="manager_lms_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False, party=person_a2,
        )
        c = Client()
        c.force_login(manager_user)
        resp = c.get(reverse("hrm:learning_team_progress"))
        assert resp.status_code == 200
        pks = [r.pk for r in resp.context["progress_rows"]]
        assert learning_progress_a.pk in pks  # employee_a reports to person_a2 (the manager)

    def test_redirects_for_user_without_employee_profile(self, member_client):
        resp = member_client.get(reverse("hrm:learning_team_progress"))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")

    def test_has_summary_and_choices_context(self, tenant_a, employment_a, person_a2, employee_a2, learning_progress_a):
        from apps.accounts.models import User
        from django.test import Client
        employment_a.manager = person_a2
        employment_a.save(update_fields=["manager"])
        manager_user = User.objects.create_user(
            email="manager_lms2@acme.com", username="manager_lms_acme2", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=False, party=person_a2,
        )
        c = Client()
        c.force_login(manager_user)
        resp = c.get(reverse("hrm:learning_team_progress"))
        assert "summary" in resp.context
        assert "status_choices" in resp.context
        assert "courses" in resp.context
        assert resp.context["summary"]["total"] >= 1


# ================================================================ TrainingCourse cross-touch (3.22 <-> 3.23)
class TestTrainingCourseDetailListsContentItems:
    def test_detail_context_has_content_items(self, client_a, training_course_a, content_item_a):
        resp = client_a.get(reverse("hrm:trainingcourse_detail", args=[training_course_a.pk]))
        assert "content_items" in resp.context
        pks = [ci.pk for ci in resp.context["content_items"]]
        assert content_item_a.pk in pks

    def test_detail_page_renders_content_item_title(self, client_a, training_course_a, content_item_a):
        resp = client_a.get(reverse("hrm:trainingcourse_detail", args=[training_course_a.pk]))
        assert b"Intro Video" in resp.content


class TestTrainingCourseDeleteProtectedByLmsReferences:
    def test_delete_blocked_when_learning_path_item_exists(self, client_a, training_course_a, path_item_a):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_delete", args=[training_course_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:trainingcourse_detail", args=[training_course_a.pk])
        assert TrainingCourse.objects.filter(pk=training_course_a.pk).exists()

    def test_delete_blocked_when_learning_progress_exists(self, client_a, training_course_a, learning_progress_a):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_delete", args=[training_course_a.pk]))
        assert resp.status_code == 302
        assert TrainingCourse.objects.filter(pk=training_course_a.pk).exists()

    def test_delete_blocked_shows_generalized_message(self, client_a, training_course_a, path_item_a):
        resp = client_a.post(reverse("hrm:trainingcourse_delete", args=[training_course_a.pk]), follow=True)
        texts = [str(m) for m in resp.context["messages"]]
        assert any("learning paths" in t and "learner" in t for t in texts)
