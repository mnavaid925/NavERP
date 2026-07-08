"""Tests for HRM 3.22 Training Management models: TrainingCourse (TRC-; clean() certification-name-
required + no-self-prerequisite) and TrainingSession (TRS-; clean() end>start + mode-specific required
fields (venue/meeting_link/external vendor-or-instructor) + the instructor/venue double-booking overlap
guard that ignores cancelled/postponed sessions; derived can_join/is_upcoming), plus TrainingSessionForm
(the create-path overlap-guard regression pin + external_vendor/currency queryset scoping). Per-tenant
sequence + unique_together on `number` for both models."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h, mi):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


# ================================================================ TrainingCourse
class TestTrainingCourseModel:
    def test_default_category_is_technical(self, training_course_a):
        assert training_course_a.category == "technical"

    def test_default_delivery_mode_is_classroom(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse.objects.create(tenant=tenant_a, title="Default Mode Course")
        assert c.delivery_mode == "classroom"

    def test_default_provider_type_is_internal(self, training_course_a):
        assert training_course_a.provider_type == "internal"

    def test_default_is_active_true(self, training_course_a):
        assert training_course_a.is_active is True

    def test_default_is_certification_false(self, training_course_a):
        assert training_course_a.is_certification is False

    def test_default_duration_hours_zero(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse.objects.create(tenant=tenant_a, title="No Duration Course")
        assert c.duration_hours == Decimal("0")

    def test_number_prefix(self, training_course_a):
        assert training_course_a.number.startswith("TRC-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c1 = TrainingCourse.objects.create(tenant=tenant_a, title="Course A")
        c2 = TrainingCourse.objects.create(tenant=tenant_a, title="Course B")
        assert c1.number != c2.number
        assert c1.number.startswith("TRC-")
        assert c2.number.startswith("TRC-")

    def test_unique_together_tenant_number(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingCourse
        with pytest.raises(IntegrityError):
            TrainingCourse.objects.create(
                tenant=tenant_a, number=training_course_a.number, title="Duplicate number",
            )

    def test_str_contains_number_and_title(self, training_course_a):
        s = str(training_course_a)
        assert training_course_a.number in s
        assert "Advanced Python" in s

    def test_str_falls_back_to_title_when_no_number(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse(tenant=tenant_a, title="Unsaved Course")
        assert str(c) == "Unsaved Course"

    # -------------------------------------------------- clean(): is_certification requires certification_name
    def test_clean_rejects_certification_without_name(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse(tenant=tenant_a, title="Cert Course", is_certification=True, certification_name="")
        with pytest.raises(ValidationError) as exc:
            c.clean()
        assert "certification_name" in exc.value.message_dict

    def test_clean_rejects_certification_with_whitespace_only_name(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse(tenant=tenant_a, title="Cert Course", is_certification=True, certification_name="   ")
        with pytest.raises(ValidationError):
            c.clean()

    def test_clean_allows_certification_with_name(self, tenant_a):
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse(
            tenant=tenant_a, title="Cert Course", is_certification=True,
            certification_name="Certified Widget Installer")
        c.clean()  # must not raise

    def test_clean_allows_non_certification_without_name(self, training_course_a):
        training_course_a.clean()  # must not raise

    # -------------------------------------------------- clean(): no self-prerequisite
    def test_clean_rejects_self_prerequisite_on_saved_instance(self, training_course_a):
        training_course_a.prerequisite_course_id = training_course_a.pk
        with pytest.raises(ValidationError) as exc:
            training_course_a.clean()
        assert "prerequisite_course" in exc.value.message_dict

    def test_clean_allows_different_prerequisite(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingCourse
        other = TrainingCourse.objects.create(tenant=tenant_a, title="Intro Python")
        training_course_a.prerequisite_course = other
        training_course_a.clean()  # must not raise

    def test_clean_allows_no_prerequisite(self, training_course_a):
        training_course_a.clean()  # must not raise (prerequisite_course_id is None)

    def test_clean_self_prerequisite_not_checked_on_unsaved_instance(self, tenant_a):
        """The guard is keyed on `self.pk` — an unsaved instance (pk=None) can't collide with itself
        (prerequisite_course_id would need a real pk to equal anyway)."""
        from apps.hrm.models import TrainingCourse
        c = TrainingCourse(tenant=tenant_a, title="Unsaved")
        c.clean()  # must not raise

    # -------------------------------------------------- FK on_delete behavior
    def test_course_delete_protected_when_sessions_exist(self, tenant_a, training_course_a, employee_a):
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 17, 0),
            venue_name="Room X",
        )
        with pytest.raises(ProtectedError):
            training_course_a.delete()

    def test_prerequisite_course_set_null_on_delete(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingCourse
        prereq = TrainingCourse.objects.create(tenant=tenant_a, title="Prereq Course")
        training_course_a.prerequisite_course = prereq
        training_course_a.save(update_fields=["prerequisite_course"])
        prereq.delete()
        training_course_a.refresh_from_db()
        assert training_course_a.prerequisite_course_id is None


# ================================================================ TrainingSession
class TestTrainingSessionModel:
    def test_default_status_is_scheduled(self, training_session_a):
        assert training_session_a.status == "scheduled"

    def test_default_delivery_mode_is_classroom(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a,
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 17, 0),
            venue_name="Room X",
        )
        assert s.delivery_mode == "classroom"

    def test_default_capacity_20(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 17, 0),
            meeting_link="https://zoom.us/j/1",
        )
        assert s.capacity == 20

    def test_default_waitlist_enabled_false(self, training_session_a):
        assert training_session_a.waitlist_enabled is False

    def test_default_timezone_utc(self, training_session_a):
        assert training_session_a.timezone == "UTC"

    def test_number_prefix(self, training_session_a):
        assert training_session_a.number.startswith("TRS-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        common = dict(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            meeting_link="https://zoom.us/j/1",
        )
        s1 = TrainingSession.objects.create(
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0), **common)
        s2 = TrainingSession.objects.create(
            start_datetime=_dt(2026, 8, 2, 9, 0), end_datetime=_dt(2026, 8, 2, 10, 0), **common)
        assert s1.number != s2.number
        assert s1.number.startswith("TRS-")
        assert s2.number.startswith("TRS-")

    def test_unique_together_tenant_number(self, tenant_a, training_session_a):
        from apps.hrm.models import TrainingSession
        with pytest.raises(IntegrityError):
            TrainingSession.objects.create(
                tenant=tenant_a, number=training_session_a.number, course=training_session_a.course,
                delivery_mode="virtual", meeting_link="https://zoom.us/j/dup",
                start_datetime=_dt(2026, 9, 1, 9, 0), end_datetime=_dt(2026, 9, 1, 10, 0),
            )

    def test_str_contains_number_and_course_title(self, training_session_a):
        s = str(training_session_a)
        assert training_session_a.number in s
        assert "Advanced Python" in s

    def test_str_falls_back_to_number_when_no_course(self, tenant_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(tenant=tenant_a, number="TRS-00099")
        assert str(s) == "TRS-00099"

    # -------------------------------------------------- clean(): end_datetime > start_datetime
    def test_clean_rejects_end_equal_start(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 9, 0),
            venue_name="Room 1",
        )
        with pytest.raises(ValidationError) as exc:
            s.clean()
        assert "end_datetime" in exc.value.message_dict

    def test_clean_rejects_end_before_start(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 8, 0),
            venue_name="Room 1",
        )
        with pytest.raises(ValidationError):
            s.clean()

    def test_clean_allows_end_after_start(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            venue_name="Room 1",
        )
        s.clean()  # must not raise

    # -------------------------------------------------- clean(): mode-specific required fields
    def test_clean_rejects_classroom_without_venue(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            venue_name="",
        )
        with pytest.raises(ValidationError) as exc:
            s.clean()
        assert "venue_name" in exc.value.message_dict

    def test_clean_rejects_virtual_without_meeting_link(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            meeting_link="",
        )
        with pytest.raises(ValidationError) as exc:
            s.clean()
        assert "meeting_link" in exc.value.message_dict

    def test_clean_allows_virtual_with_meeting_link(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            meeting_link="https://zoom.us/j/123",
        )
        s.clean()  # must not raise

    def test_clean_rejects_external_without_vendor_or_instructor_name(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="external",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
        )
        with pytest.raises(ValidationError) as exc:
            s.clean()
        assert "external_vendor" in exc.value.message_dict

    def test_clean_allows_external_with_named_instructor_only(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="external",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            external_instructor_name="Jane Trainer",
        )
        s.clean()  # must not raise

    def test_clean_allows_external_with_vendor_only(self, tenant_a, training_course_a):
        from apps.core.models import Party, PartyRole
        from apps.hrm.models import TrainingSession
        vendor = Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Training Co")
        PartyRole.objects.create(tenant=tenant_a, party=vendor, role="vendor")
        s = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="external",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            external_vendor=vendor,
        )
        s.clean()  # must not raise

    # -------------------------------------------------- clean(): double-booking overlap guard
    def test_clean_rejects_instructor_double_booking_overlap(self, tenant_a, training_course_a, employee_a):
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 1", instructor_employee=employee_a,
        )
        overlapping = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 11, 0), end_datetime=_dt(2026, 8, 1, 14, 0),
            venue_name="Room 2", instructor_employee=employee_a,
        )
        with pytest.raises(ValidationError) as exc:
            overlapping.clean()
        assert "instructor_employee" in exc.value.message_dict

    def test_clean_rejects_venue_double_booking_overlap_case_insensitive(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 101",
        )
        overlapping = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 10, 0), end_datetime=_dt(2026, 8, 1, 13, 0),
            venue_name="room 101",  # different case — must still match (iexact)
        )
        with pytest.raises(ValidationError) as exc:
            overlapping.clean()
        assert "venue_name" in exc.value.message_dict

    def test_cancelled_session_does_not_block_instructor_overlap(self, tenant_a, training_course_a, employee_a):
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="cancelled",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 1", instructor_employee=employee_a,
        )
        overlapping = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 10, 0), end_datetime=_dt(2026, 8, 1, 13, 0),
            venue_name="Room 2", instructor_employee=employee_a,
        )
        overlapping.clean()  # must not raise — cancelled sessions never conflict

    def test_postponed_session_does_not_block_venue_overlap(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="postponed",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 1",
        )
        overlapping = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 10, 0), end_datetime=_dt(2026, 8, 1, 13, 0),
            venue_name="Room 1",
        )
        overlapping.clean()  # must not raise — postponed sessions never conflict

    def test_non_overlapping_different_day_is_fine(self, tenant_a, training_course_a, employee_a):
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 1", instructor_employee=employee_a,
        )
        other_day = TrainingSession(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 2, 9, 0), end_datetime=_dt(2026, 8, 2, 12, 0),
            venue_name="Room 1", instructor_employee=employee_a,
        )
        other_day.clean()  # must not raise — different day, no overlap

    def test_clean_editing_existing_session_does_not_conflict_with_itself(self, training_session_a):
        training_session_a.clean()  # must not raise — the overlap query excludes its own pk

    # -------------------------------------------------- derived: can_join
    def test_can_join_false_without_meeting_link(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom",
            start_datetime=now - datetime.timedelta(minutes=5), end_datetime=now + datetime.timedelta(hours=1),
            venue_name="Room 1",
        )
        assert s.can_join is False

    def test_can_join_true_within_window(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=now - datetime.timedelta(minutes=5), end_datetime=now + datetime.timedelta(hours=1),
            meeting_link="https://zoom.us/j/123",
        )
        assert s.can_join is True

    def test_can_join_true_at_the_15_minute_boundary(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=now + datetime.timedelta(minutes=15), end_datetime=now + datetime.timedelta(hours=1),
            meeting_link="https://zoom.us/j/123",
        )
        assert s.can_join is True

    def test_can_join_false_before_window(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=now + datetime.timedelta(minutes=30), end_datetime=now + datetime.timedelta(hours=1),
            meeting_link="https://zoom.us/j/123",
        )
        assert s.can_join is False

    def test_can_join_false_after_end(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="virtual",
            start_datetime=now - datetime.timedelta(hours=3), end_datetime=now - datetime.timedelta(hours=1),
            meeting_link="https://zoom.us/j/123",
        )
        assert s.can_join is False

    # -------------------------------------------------- derived: is_upcoming
    def test_is_upcoming_true_when_scheduled_and_future(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=now + datetime.timedelta(days=1), end_datetime=now + datetime.timedelta(days=1, hours=8),
            venue_name="Room 1",
        )
        assert s.is_upcoming is True

    def test_is_upcoming_false_when_completed_even_if_future(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="completed",
            start_datetime=now + datetime.timedelta(days=1), end_datetime=now + datetime.timedelta(days=1, hours=8),
            venue_name="Room 1",
        )
        assert s.is_upcoming is False

    def test_is_upcoming_false_when_cancelled(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="cancelled",
            start_datetime=now + datetime.timedelta(days=1), end_datetime=now + datetime.timedelta(days=1, hours=8),
            venue_name="Room 1",
        )
        assert s.is_upcoming is False

    def test_is_upcoming_false_when_start_in_past(self, tenant_a, training_course_a):
        from apps.hrm.models import TrainingSession
        now = timezone.now()
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=now - datetime.timedelta(days=1), end_datetime=now - datetime.timedelta(hours=20),
            venue_name="Room 1",
        )
        assert s.is_upcoming is False

    # -------------------------------------------------- FK on_delete behavior
    def test_instructor_employee_set_null_on_delete(self, training_session_a, employee_a):
        employee_a.delete()
        training_session_a.refresh_from_db()
        assert training_session_a.instructor_employee_id is None

    def test_external_vendor_set_null_on_delete(self, tenant_a, training_course_a):
        from apps.core.models import Party, PartyRole
        from apps.hrm.models import TrainingSession
        vendor = Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Training Co")
        PartyRole.objects.create(tenant=tenant_a, party=vendor, role="vendor")
        s = TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="external",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 10, 0),
            external_vendor=vendor,
        )
        vendor.delete()
        s.refresh_from_db()
        assert s.external_vendor_id is None

    def test_course_delete_protected(self, training_session_a, training_course_a):
        with pytest.raises(ProtectedError):
            training_course_a.delete()


# ================================================================ TrainingSessionForm
def _session_form_data(course, **overrides):
    data = {
        "course": course.pk,
        "delivery_mode": "classroom",
        "status": "scheduled",
        "start_datetime": "2026-08-01T09:00",
        "end_datetime": "2026-08-01T12:00",
        "timezone": "UTC",
        "capacity": "20",
        "venue_name": "Room 101",
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


class TestTrainingSessionFormOverlapRegression:
    """Regression pin: TrainingSessionForm.__init__ sets ``self.instance.tenant`` BEFORE validation
    so the model's clean() double-booking overlap query is tenant-scoped even on CREATE (crud_create
    only sets obj.tenant AFTER form.is_valid()). Without that fix this guard silently never fires
    on the create path."""

    def test_new_session_overlapping_same_instructor_rejected(self, tenant_a, training_course_a, employee_a):
        from apps.hrm.forms import TrainingSessionForm
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 1", instructor_employee=employee_a,
        )
        data = _session_form_data(
            training_course_a,
            start_datetime="2026-08-01T11:00", end_datetime="2026-08-01T14:00",
            venue_name="Room 2", instructor_employee=str(employee_a.pk),
        )
        form = TrainingSessionForm(data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "instructor_employee" in form.errors

    def test_new_session_non_overlapping_same_instructor_is_valid(self, tenant_a, training_course_a, employee_a):
        from apps.hrm.forms import TrainingSessionForm
        from apps.hrm.models import TrainingSession
        TrainingSession.objects.create(
            tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 12, 0),
            venue_name="Room 1", instructor_employee=employee_a,
        )
        data = _session_form_data(
            training_course_a,
            start_datetime="2026-08-02T09:00", end_datetime="2026-08-02T12:00",
            venue_name="Room 2", instructor_employee=str(employee_a.pk),
        )
        form = TrainingSessionForm(data, tenant=tenant_a)
        assert form.is_valid() is True, form.errors


class TestTrainingSessionFormQuerysetScoping:
    def test_external_vendor_queryset_limited_to_vendor_role_parties(self, tenant_a, training_course_a):
        from apps.core.models import Party, PartyRole
        from apps.hrm.forms import TrainingSessionForm
        vendor = Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Training Co")
        PartyRole.objects.create(tenant=tenant_a, party=vendor, role="vendor")
        customer = Party.objects.create(tenant=tenant_a, kind="organization", name="Not A Vendor Inc")
        PartyRole.objects.create(tenant=tenant_a, party=customer, role="customer")
        form = TrainingSessionForm(tenant=tenant_a)
        pks = list(form.fields["external_vendor"].queryset.values_list("pk", flat=True))
        assert vendor.pk in pks
        assert customer.pk not in pks

    def test_external_vendor_queryset_excludes_other_tenant_vendors(self, tenant_a, tenant_b, training_course_a):
        from apps.core.models import Party, PartyRole
        from apps.hrm.forms import TrainingSessionForm
        vendor_b = Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Training Co")
        PartyRole.objects.create(tenant=tenant_b, party=vendor_b, role="vendor")
        form = TrainingSessionForm(tenant=tenant_a)
        pks = list(form.fields["external_vendor"].queryset.values_list("pk", flat=True))
        assert vendor_b.pk not in pks

    def test_currency_queryset_is_global_active_set(self, tenant_a):
        from apps.accounting.models import Currency
        from apps.hrm.forms import TrainingSessionForm
        usd = Currency.objects.create(code="USD", name="US Dollar", is_active=True)
        inactive = Currency.objects.create(code="ZZZ", name="Inactive Currency", is_active=False)
        form = TrainingSessionForm(tenant=tenant_a)
        pks = list(form.fields["currency"].queryset.values_list("pk", flat=True))
        assert usd.pk in pks
        assert inactive.pk not in pks

    def test_currency_queryset_not_tenant_filtered(self, tenant_a, tenant_b):
        """Currency has no tenant FK — the SAME global active set is offered regardless of which
        tenant the form is bound to."""
        from apps.accounting.models import Currency
        from apps.hrm.forms import TrainingSessionForm
        usd = Currency.objects.create(code="USD", name="US Dollar", is_active=True)
        form_a = TrainingSessionForm(tenant=tenant_a)
        form_b = TrainingSessionForm(tenant=tenant_b)
        assert usd.pk in list(form_a.fields["currency"].queryset.values_list("pk", flat=True))
        assert usd.pk in list(form_b.fields["currency"].queryset.values_list("pk", flat=True))
