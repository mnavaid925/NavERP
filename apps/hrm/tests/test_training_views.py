"""Tests for HRM 3.22 Training Management views: TrainingCourse CRUD (+ ProtectedError-guarded
delete when sessions exist) and TrainingSession CRUD (classroom/virtual/external creation, the
double-booking overlap rejection at the view layer), plus the Training Calendar (date-grouped,
?delivery_mode / ?status / ?from / ?to filters, cancelled always excluded). Training is ordinary
tenant-scoped CRUD — no confidentiality gate (open to every authenticated tenant user, mirrors 3.2
Designation/JobGrade). Mirrors test_improvement_views.py conventions — client_a is the tenant admin."""
import datetime

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h, mi):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


def _session_post_data(course, **overrides):
    data = {
        "course": course.pk,
        "delivery_mode": "classroom",
        "status": "scheduled",
        "start_datetime": "2026-09-01T09:00",
        "end_datetime": "2026-09-01T17:00",
        "timezone": "UTC",
        "capacity": "20",
        "waitlist_enabled": "",
        "venue_name": "Main Hall",
        "venue_address": "",
        "meeting_platform": "",
        "meeting_link": "",
        "meeting_id": "",
        "instructor_employee": "",
        "external_instructor_name": "",
        "external_vendor": "",
        "estimated_cost": "",
        "actual_cost": "",
        "currency": "",
        "invoice_reference": "",
        "notes": "",
    }
    data.update(overrides)
    return data


def _course_post_data(**overrides):
    data = {
        "title": "Onboarding Basics", "description": "", "category": "onboarding",
        "delivery_mode": "classroom", "provider_type": "internal", "duration_hours": "4",
        "is_certification": "", "certification_name": "", "certification_validity_months": "",
        "prerequisite_course": "", "default_capacity": "15", "is_active": "on",
    }
    data.update(overrides)
    return data


# ================================================================ TrainingCourse CRUD
class TestTrainingCourseListView:
    def test_list_200(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks

    def test_list_filter_by_category(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"category": "technical"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks

    def test_list_filter_by_category_excludes_other(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"category": "safety"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk not in pks

    def test_list_filter_by_delivery_mode(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"delivery_mode": "classroom"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks

    def test_list_filter_by_is_active_true(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"is_active": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks

    def test_list_filter_by_is_active_false_excludes(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"is_active": "False"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk not in pks

    def test_list_search_by_number(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"q": training_course_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks

    def test_list_search_by_title(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"q": "Advanced Python"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_course_a.pk in pks

    def test_list_has_choices_context(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"))
        assert "category_choices" in resp.context
        assert "provider_type_choices" in resp.context
        assert "delivery_mode_choices" in resp.context

    def test_bad_is_active_filter_does_not_500(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"is_active": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, training_course_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:trainingcourse_list"))


class TestTrainingCourseCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:trainingcourse_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_create"), _course_post_data())
        assert resp.status_code == 302
        course = TrainingCourse.objects.filter(tenant=tenant_a, title="Onboarding Basics").first()
        assert course is not None
        assert course.tenant_id == tenant_a.pk
        assert course.number.startswith("TRC-")

    def test_post_certification_without_name_rejected(self, client_a, tenant_a):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_create"), _course_post_data(
            title="Cert Course", is_certification="on", certification_name="",
        ))
        assert resp.status_code == 200
        assert not TrainingCourse.objects.filter(tenant=tenant_a, title="Cert Course").exists()

    def test_post_certification_with_name_succeeds(self, client_a, tenant_a):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_create"), _course_post_data(
            title="Cert Course 2", is_certification="on", certification_name="Certified Widget Installer",
        ))
        assert resp.status_code == 302
        assert TrainingCourse.objects.filter(tenant=tenant_a, title="Cert Course 2").exists()

    def test_form_has_no_tenant_or_number_field(self, client_a):
        resp = client_a.get(reverse("hrm:trainingcourse_create"))
        fields = resp.context["form"].fields
        assert "tenant" not in fields
        assert "number" not in fields

    def test_prerequisite_dropdown_scoped_to_tenant(self, client_a, training_course_a, training_course_b):
        resp = client_a.get(reverse("hrm:trainingcourse_create"))
        pks = list(resp.context["form"].fields["prerequisite_course"].queryset.values_list("pk", flat=True))
        assert training_course_a.pk in pks
        assert training_course_b.pk not in pks


class TestTrainingCourseDetailEditDelete:
    def test_detail_200(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_detail", args=[training_course_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_detail", args=[training_course_a.pk]))
        for key in ("obj", "sessions", "unlocks"):
            assert key in resp.context

    def test_detail_lists_sessions(self, client_a, training_course_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingcourse_detail", args=[training_course_a.pk]))
        pks = [s.pk for s in resp.context["sessions"]]
        assert training_session_a.pk in pks

    def test_edit_get_200(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_edit", args=[training_course_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_title(self, client_a, training_course_a):
        resp = client_a.post(reverse("hrm:trainingcourse_edit", args=[training_course_a.pk]), _course_post_data(
            title="Advanced Python (Updated)", category="technical", duration_hours="16",
            default_capacity="20",
        ))
        assert resp.status_code == 302
        training_course_a.refresh_from_db()
        assert training_course_a.title == "Advanced Python (Updated)"

    def test_prerequisite_dropdown_excludes_self_on_edit(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_edit", args=[training_course_a.pk]))
        pks = list(resp.context["form"].fields["prerequisite_course"].queryset.values_list("pk", flat=True))
        assert training_course_a.pk not in pks

    def test_delete_no_sessions_removes(self, client_a, tenant_a):
        from apps.hrm.models import TrainingCourse
        course = TrainingCourse.objects.create(tenant=tenant_a, title="Deletable Course")
        resp = client_a.post(reverse("hrm:trainingcourse_delete", args=[course.pk]))
        assert resp.status_code == 302
        assert not TrainingCourse.objects.filter(pk=course.pk).exists()

    def test_delete_with_sessions_redirects_and_survives(self, client_a, training_course_a, training_session_a):
        from apps.hrm.models import TrainingCourse
        resp = client_a.post(reverse("hrm:trainingcourse_delete", args=[training_course_a.pk]))
        assert resp.status_code == 302
        assert TrainingCourse.objects.filter(pk=training_course_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, training_course_a):
        resp = client_a.get(reverse("hrm:trainingcourse_delete", args=[training_course_a.pk]))
        assert resp.status_code == 405


# ================================================================ TrainingSession CRUD
class TestTrainingSessionListView:
    def test_list_200(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks

    def test_list_filter_by_delivery_mode_virtual_returns_only_virtual(
        self, client_a, tenant_a, training_course_a, training_session_a
    ):
        from apps.hrm.models import TrainingSession
        virtual = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual", status="scheduled",
            start_datetime=_dt(2026, 8, 5, 9, 0), end_datetime=_dt(2026, 8, 5, 11, 0),
            meeting_link="https://zoom.us/j/999",
        )
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"delivery_mode": "virtual"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert virtual.pk in pks
        assert training_session_a.pk not in pks  # training_session_a is classroom

    def test_list_filter_by_status(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"status": "scheduled"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks

    def test_list_filter_by_course(self, client_a, training_course_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"course": training_course_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks

    def test_list_filter_by_instructor(self, client_a, employee_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"instructor_employee": employee_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks

    def test_list_search_by_number(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"q": training_session_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks

    def test_list_search_by_venue(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"q": "Room 101"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert training_session_a.pk in pks

    def test_list_has_choices_context(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"))
        assert "status_choices" in resp.context
        assert "delivery_mode_choices" in resp.context
        assert "courses" in resp.context
        assert "instructors" in resp.context

    def test_bad_course_filter_does_not_500(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"course": "abc"})
        assert resp.status_code == 200

    def test_bad_instructor_filter_does_not_500(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"instructor_employee": "abc"})
        assert resp.status_code == 200

    def test_bad_page_does_not_500(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, training_session_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:trainingsession_list"))


class TestTrainingSessionCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:trainingsession_create"))
        assert resp.status_code == 200

    def test_post_creates_classroom_session_with_tenant(self, client_a, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        resp = client_a.post(reverse("hrm:trainingsession_create"), _session_post_data(training_course_a))
        assert resp.status_code == 302
        session = TrainingSession.objects.filter(tenant=tenant_a, course=training_course_a).first()
        assert session is not None
        assert session.tenant_id == tenant_a.pk
        assert session.number.startswith("TRS-")
        assert session.status == "scheduled"

    def test_post_creates_virtual_session(self, client_a, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        data = _session_post_data(
            training_course_a, delivery_mode="virtual", venue_name="",
            meeting_link="https://zoom.us/j/12345",
        )
        resp = client_a.post(reverse("hrm:trainingsession_create"), data)
        assert resp.status_code == 302
        assert TrainingSession.objects.filter(tenant=tenant_a, delivery_mode="virtual").exists()

    def test_post_creates_external_session_with_named_instructor(self, client_a, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        data = _session_post_data(
            training_course_a, delivery_mode="external", venue_name="",
            external_instructor_name="Jane Trainer",
        )
        resp = client_a.post(reverse("hrm:trainingsession_create"), data)
        assert resp.status_code == 302
        assert TrainingSession.objects.filter(tenant=tenant_a, delivery_mode="external").exists()

    def test_post_overlapping_instructor_rejected(
        self, client_a, tenant_a, training_course_a, training_session_a, employee_a
    ):
        data = _session_post_data(
            training_course_a,
            start_datetime="2026-07-20T12:00", end_datetime="2026-07-20T18:00",
            venue_name="Room 999", instructor_employee=str(employee_a.pk),
        )
        resp = client_a.post(reverse("hrm:trainingsession_create"), data)
        assert resp.status_code == 200
        assert "instructor_employee" in resp.context["form"].errors

    def test_form_has_no_tenant_or_number_field(self, client_a):
        resp = client_a.get(reverse("hrm:trainingsession_create"))
        fields = resp.context["form"].fields
        assert "tenant" not in fields
        assert "number" not in fields


class TestTrainingSessionDetailEditDelete:
    def test_detail_200(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_detail", args=[training_session_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_obj(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_detail", args=[training_session_a.pk]))
        assert "obj" in resp.context
        assert resp.context["obj"].pk == training_session_a.pk

    def test_edit_get_200(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_edit", args=[training_session_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_venue(self, client_a, training_session_a, training_course_a, employee_a):
        data = _session_post_data(
            training_course_a,
            start_datetime="2026-07-20T09:00", end_datetime="2026-07-20T17:00",
            venue_name="Room 202", instructor_employee=str(employee_a.pk),
        )
        resp = client_a.post(reverse("hrm:trainingsession_edit", args=[training_session_a.pk]), data)
        assert resp.status_code == 302
        training_session_a.refresh_from_db()
        assert training_session_a.venue_name == "Room 202"

    def test_delete_post_removes(self, client_a, training_session_a):
        from apps.hrm.models import TrainingSession
        pk = training_session_a.pk
        resp = client_a.post(reverse("hrm:trainingsession_delete", args=[pk]))
        assert resp.status_code == 302
        assert not TrainingSession.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:trainingsession_delete", args=[training_session_a.pk]))
        assert resp.status_code == 405


# ================================================================ Training Calendar
class TestTrainingCalendar:
    def test_calendar_200(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"))
        assert resp.status_code == 200

    def test_calendar_groups_sessions_by_date(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"), {"from": "2026-07-01"})
        all_sessions = [s for _, sessions in resp.context["sessions_by_date"] for s in sessions]
        assert training_session_a in all_sessions

    def test_calendar_excludes_cancelled_by_default(self, client_a, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        cancelled = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="cancelled",
            start_datetime=_dt(2026, 8, 10, 9, 0), end_datetime=_dt(2026, 8, 10, 11, 0),
            venue_name="Room X",
        )
        resp = client_a.get(reverse("hrm:training_calendar"), {"from": "2026-08-01"})
        all_sessions = [s for _, sessions in resp.context["sessions_by_date"] for s in sessions]
        assert cancelled not in all_sessions

    def test_calendar_respects_delivery_mode_filter(
        self, client_a, tenant_a, training_course_a, training_session_a
    ):
        from apps.hrm.models import TrainingSession
        virtual = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual", status="scheduled",
            start_datetime=_dt(2026, 7, 21, 9, 0), end_datetime=_dt(2026, 7, 21, 11, 0),
            meeting_link="https://zoom.us/j/1",
        )
        resp = client_a.get(reverse("hrm:training_calendar"), {
            "delivery_mode": "virtual", "from": "2026-07-01",
        })
        all_sessions = [s for _, sessions in resp.context["sessions_by_date"] for s in sessions]
        assert virtual in all_sessions
        assert training_session_a not in all_sessions

    def test_calendar_respects_status_filter(self, client_a, tenant_a, training_course_a, training_session_a):
        from apps.hrm.models import TrainingSession
        confirmed = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="confirmed",
            start_datetime=_dt(2026, 7, 22, 9, 0), end_datetime=_dt(2026, 7, 22, 11, 0),
            venue_name="Room Y",
        )
        resp = client_a.get(reverse("hrm:training_calendar"), {
            "status": "confirmed", "from": "2026-07-01",
        })
        all_sessions = [s for _, sessions in resp.context["sessions_by_date"] for s in sessions]
        assert confirmed in all_sessions
        assert training_session_a not in all_sessions  # scheduled, filtered out by ?status=confirmed

    def test_calendar_respects_from_and_to_range(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"), {
            "from": "2026-07-25", "to": "2026-07-30",
        })
        all_sessions = [s for _, sessions in resp.context["sessions_by_date"] for s in sessions]
        assert training_session_a not in all_sessions  # training_session_a is 2026-07-20, before the range

    def test_calendar_to_upper_bound_is_inclusive(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"), {
            "from": "2026-07-20", "to": "2026-07-20",
        })
        all_sessions = [s for _, sessions in resp.context["sessions_by_date"] for s in sessions]
        assert training_session_a in all_sessions

    def test_calendar_bad_date_input_does_not_500(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"), {"from": "not-a-date", "to": "also-bad"})
        assert resp.status_code == 200

    def test_calendar_status_choices_excludes_cancelled(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"))
        values = [v for v, _ in resp.context["status_choices"]]
        assert "cancelled" not in values

    def test_calendar_has_delivery_mode_choices_context(self, client_a, training_session_a):
        resp = client_a.get(reverse("hrm:training_calendar"))
        assert "delivery_mode_choices" in resp.context
        assert "from_date" in resp.context
        assert "to_date" in resp.context
