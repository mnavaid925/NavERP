"""Tests for HRM 3.23 Learning Management (LMS) models: ``LearningContentItem`` (clean() enforces the
one content-payload field matching content_type — video/document/scorm/external_link/text each need
their own field, "assessment" needs none of them), ``LearningPath`` (LNP- auto-number, per-tenant
sequence, unique_together), ``LearningPathItem`` (clean() prerequisite-sequencing guard that reuses
``TrainingCourse.prerequisite_course`` — no new rule table), and ``LearningProgress`` (clean()
completed>=started guard, derived ``certification_expires_on``/``is_certification_expired`` month-math,
__str__), plus the leaderboard's ``_lms_level_for_points`` threshold helper.

Also pins the two review-caught form bugs: ``LearningProgressForm``'s (employee, course) duplicate
guard and ``LearningPathItemForm``'s (path, course) duplicate guard — Django's ModelForm
``validate_unique()`` SKIPS a unique_together constraint when any of its fields (here: ``tenant``, and
for the path item also ``path``) is excluded from the form, so without the explicit form-level check a
re-add would surface as a raw IntegrityError 500 instead of a clean form error."""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h=0, mi=0):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


# ================================================================ LearningContentItem
class TestLearningContentItemModel:
    def test_default_content_type_video(self, content_item_a):
        assert content_item_a.content_type == "video"

    def test_default_sequence(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem.objects.create(
            tenant=tenant_a, course=training_course_a, title="No Sequence",
            content_type="text", body_text="Some text",
        )
        assert item.sequence == 0

    def test_default_is_required_true(self, content_item_a):
        assert content_item_a.is_required is True

    def test_default_pass_threshold_percent_70(self, content_item_a):
        assert content_item_a.pass_threshold_percent == 70

    def test_default_max_attempts_1(self, content_item_a):
        assert content_item_a.max_attempts == 1

    def test_str_contains_course_title_and_sequence_and_title(self, content_item_a):
        s = str(content_item_a)
        assert "Advanced Python" in s
        assert "1" in s
        assert "Intro Video" in s

    def test_str_falls_back_to_title_when_no_course(self, tenant_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(tenant=tenant_a, title="Orphan Lesson")
        assert str(item) == "Orphan Lesson"

    # -------------------------------------------------- clean(): content-type-specific payload
    def test_clean_video_requires_video_url(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Video Lesson",
            content_type="video", video_url="",
        )
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "video_url" in exc.value.message_dict

    def test_clean_video_with_url_valid(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Video Lesson",
            content_type="video", video_url="https://example.com/v.mp4",
        )
        item.clean()  # must not raise

    def test_clean_document_requires_document_file(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Doc Lesson", content_type="document",
        )
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "document_file" in exc.value.message_dict

    def test_clean_document_with_file_valid(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Doc Lesson", content_type="document",
            document_file=SimpleUploadedFile("notes.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        item.clean()  # must not raise

    def test_clean_scorm_requires_scorm_package(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="SCORM Lesson", content_type="scorm",
        )
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "scorm_package" in exc.value.message_dict

    def test_clean_scorm_with_package_valid(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="SCORM Lesson", content_type="scorm",
            scorm_package=SimpleUploadedFile("package.zip", b"PK\x03\x04 test", content_type="application/zip"),
        )
        item.clean()  # must not raise

    def test_clean_external_link_requires_external_url(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Link Lesson", content_type="external_link",
        )
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "external_url" in exc.value.message_dict

    def test_clean_external_link_with_url_valid(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Link Lesson", content_type="external_link",
            external_url="https://example.com/resource",
        )
        item.clean()  # must not raise

    def test_clean_text_requires_body_text(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Text Lesson", content_type="text",
        )
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "body_text" in exc.value.message_dict

    def test_clean_text_requires_body_text_rejects_whitespace_only(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Text Lesson", content_type="text",
            body_text="   ",
        )
        with pytest.raises(ValidationError):
            item.clean()

    def test_clean_text_with_body_valid(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Text Lesson", content_type="text",
            body_text="Some article content.",
        )
        item.clean()  # must not raise

    def test_clean_assessment_needs_none_of_the_content_fields(self, tenant_a, training_course_a):
        from apps.hrm.models import LearningContentItem
        item = LearningContentItem(
            tenant=tenant_a, course=training_course_a, title="Quiz", content_type="assessment",
            pass_threshold_percent=80, max_attempts=3, time_limit_minutes=30,
        )
        item.clean()  # must not raise — assessment has no required content-payload field

    # -------------------------------------------------- FK on_delete behavior
    def test_content_item_deleted_when_course_deleted(self, tenant_a, training_course_a, content_item_a):
        from apps.hrm.models import LearningContentItem
        pk = content_item_a.pk
        training_course_a.delete()
        assert not LearningContentItem.objects.filter(pk=pk).exists()


# ================================================================ LearningPath
class TestLearningPathModel:
    def test_number_prefix(self, learning_path_a):
        assert learning_path_a.number.startswith("LNP-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a):
        from apps.hrm.models import LearningPath
        p1 = LearningPath.objects.create(tenant=tenant_a, title="Path A")
        p2 = LearningPath.objects.create(tenant=tenant_a, title="Path B")
        assert p1.number != p2.number
        assert p1.number.startswith("LNP-")
        assert p2.number.startswith("LNP-")

    def test_unique_together_tenant_number(self, tenant_a, learning_path_a):
        from apps.hrm.models import LearningPath
        with pytest.raises(IntegrityError):
            LearningPath.objects.create(
                tenant=tenant_a, number=learning_path_a.number, title="Duplicate number",
            )

    def test_default_is_mandatory_false(self, learning_path_a):
        assert learning_path_a.is_mandatory is False

    def test_default_is_active_true(self, learning_path_a):
        assert learning_path_a.is_active is True

    def test_str_contains_number_and_title(self, learning_path_a):
        s = str(learning_path_a)
        assert learning_path_a.number in s
        assert "Engineering Onboarding" in s

    def test_str_falls_back_to_title_when_no_number(self, tenant_a):
        from apps.hrm.models import LearningPath
        p = LearningPath(tenant=tenant_a, title="Unsaved Path")
        assert str(p) == "Unsaved Path"


# ================================================================ LearningPathItem
class TestLearningPathItemModel:
    def test_default_is_mandatory_true(self, path_item_a):
        assert path_item_a.is_mandatory is True

    def test_default_sequence(self, tenant_a, learning_path_a):
        from apps.hrm.models import LearningPathItem, TrainingCourse
        other = TrainingCourse.objects.create(tenant=tenant_a, title="Other Course")
        item = LearningPathItem.objects.create(tenant=tenant_a, path=learning_path_a, course=other)
        assert item.sequence == 0

    def test_str_contains_path_title_sequence_and_course_title(self, path_item_a):
        s = str(path_item_a)
        assert "Engineering Onboarding" in s
        assert "Advanced Python" in s
        assert "1" in s

    def test_str_falls_back_when_missing_path_or_course(self, tenant_a):
        from apps.hrm.models import LearningPathItem
        item = LearningPathItem(tenant=tenant_a)
        s = str(item)
        assert "LearningPathItem" in s

    def test_unique_together_tenant_path_course(self, tenant_a, learning_path_a, training_course_a, path_item_a):
        from apps.hrm.models import LearningPathItem
        with pytest.raises(IntegrityError):
            LearningPathItem.objects.create(
                tenant=tenant_a, path=learning_path_a, course=training_course_a, sequence=5,
            )

    # -------------------------------------------------- clean(): prerequisite-sequencing guard
    def test_clean_no_prerequisite_no_error(self, tenant_a, learning_path_a, training_course_a):
        from apps.hrm.models import LearningPathItem
        item = LearningPathItem(tenant=tenant_a, path=learning_path_a, course=training_course_a, sequence=1)
        item.clean()  # must not raise — training_course_a has no prerequisite_course

    def test_clean_prerequisite_not_in_path_no_error(self, tenant_a, learning_path_a):
        from apps.hrm.models import LearningPathItem, TrainingCourse
        prereq = TrainingCourse.objects.create(tenant=tenant_a, title="Prereq Course")
        advanced = TrainingCourse.objects.create(
            tenant=tenant_a, title="Advanced Course", prerequisite_course=prereq)
        item = LearningPathItem(tenant=tenant_a, path=learning_path_a, course=advanced, sequence=1)
        item.clean()  # must not raise — the prerequisite isn't in this path at all

    def test_clean_prerequisite_earlier_sequence_is_valid(self, tenant_a, learning_path_a):
        from apps.hrm.models import LearningPathItem, TrainingCourse
        prereq = TrainingCourse.objects.create(tenant=tenant_a, title="Prereq Course")
        advanced = TrainingCourse.objects.create(
            tenant=tenant_a, title="Advanced Course", prerequisite_course=prereq)
        LearningPathItem.objects.create(tenant=tenant_a, path=learning_path_a, course=prereq, sequence=1)
        item = LearningPathItem(tenant=tenant_a, path=learning_path_a, course=advanced, sequence=2)
        item.clean()  # must not raise — prerequisite sits earlier (sequence 1 < 2)

    def test_clean_prerequisite_same_sequence_raises_on_sequence(self, tenant_a, learning_path_a):
        from apps.hrm.models import LearningPathItem, TrainingCourse
        prereq = TrainingCourse.objects.create(tenant=tenant_a, title="Prereq Course")
        advanced = TrainingCourse.objects.create(
            tenant=tenant_a, title="Advanced Course", prerequisite_course=prereq)
        LearningPathItem.objects.create(tenant=tenant_a, path=learning_path_a, course=prereq, sequence=2)
        item = LearningPathItem(tenant=tenant_a, path=learning_path_a, course=advanced, sequence=2)
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "sequence" in exc.value.message_dict

    def test_clean_prerequisite_later_sequence_raises_on_sequence(self, tenant_a, learning_path_a):
        from apps.hrm.models import LearningPathItem, TrainingCourse
        prereq = TrainingCourse.objects.create(tenant=tenant_a, title="Prereq Course")
        advanced = TrainingCourse.objects.create(
            tenant=tenant_a, title="Advanced Course", prerequisite_course=prereq)
        LearningPathItem.objects.create(tenant=tenant_a, path=learning_path_a, course=prereq, sequence=3)
        item = LearningPathItem(tenant=tenant_a, path=learning_path_a, course=advanced, sequence=1)
        with pytest.raises(ValidationError) as exc:
            item.clean()
        assert "sequence" in exc.value.message_dict

    def test_clean_editing_existing_item_excludes_itself(self, tenant_a, learning_path_a):
        """The prerequisite lookup excludes self.pk — re-clean()ing a saved item whose OWN course is
        the prerequisite of nothing else in the path must not self-collide."""
        from apps.hrm.models import LearningPathItem, TrainingCourse
        prereq = TrainingCourse.objects.create(tenant=tenant_a, title="Prereq Course")
        item = LearningPathItem.objects.create(tenant=tenant_a, path=learning_path_a, course=prereq, sequence=1)
        item.clean()  # must not raise

    # -------------------------------------------------- FK on_delete behavior
    def test_course_delete_protected_when_in_path(self, path_item_a, training_course_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            training_course_a.delete()

    def test_path_item_deleted_when_path_deleted(self, tenant_a, learning_path_a, path_item_a):
        from apps.hrm.models import LearningPathItem
        pk = path_item_a.pk
        learning_path_a.delete()
        assert not LearningPathItem.objects.filter(pk=pk).exists()


# ================================================================ LearningProgress
class TestLearningProgressModel:
    def test_default_status_not_started(self, learning_progress_a):
        assert learning_progress_a.status == "not_started"

    def test_default_percent_complete_zero(self, learning_progress_a):
        assert learning_progress_a.percent_complete == 0

    def test_default_time_spent_minutes_zero(self, learning_progress_a):
        assert learning_progress_a.time_spent_minutes == 0

    def test_default_attempt_count_zero(self, learning_progress_a):
        assert learning_progress_a.attempt_count == 0

    def test_default_points_earned_zero(self, learning_progress_a):
        assert learning_progress_a.points_earned == 0

    def test_default_passed_none(self, learning_progress_a):
        assert learning_progress_a.passed is None

    def test_unique_together_tenant_employee_course(self, tenant_a, employee_a, training_course_a, learning_progress_a):
        from apps.hrm.models import LearningProgress
        with pytest.raises(IntegrityError):
            LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=training_course_a)

    def test_str_contains_employee_course_and_status(self, learning_progress_a):
        s = str(learning_progress_a)
        assert "Advanced Python" in s
        assert "Not Started" in s

    def test_str_falls_back_when_missing_employee_or_course(self, tenant_a):
        from apps.hrm.models import LearningProgress
        progress = LearningProgress(tenant=tenant_a)
        s = str(progress)
        assert "?" in s

    # -------------------------------------------------- clean(): completed >= started
    def test_clean_completed_before_started_raises(self, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import LearningProgress
        progress = LearningProgress(
            tenant=tenant_a, employee=employee_a, course=training_course_a,
            started_at=_dt(2026, 7, 10, 9, 0), completed_at=_dt(2026, 7, 9, 9, 0),
        )
        with pytest.raises(ValidationError) as exc:
            progress.clean()
        assert "completed_at" in exc.value.message_dict

    def test_clean_completed_after_started_valid(self, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import LearningProgress
        progress = LearningProgress(
            tenant=tenant_a, employee=employee_a, course=training_course_a,
            started_at=_dt(2026, 7, 9, 9, 0), completed_at=_dt(2026, 7, 10, 9, 0),
        )
        progress.clean()  # must not raise

    def test_clean_no_dates_valid(self, learning_progress_a):
        learning_progress_a.clean()  # must not raise — neither started_at nor completed_at set

    # -------------------------------------------------- derived: certification_expires_on
    def test_certification_expires_on_none_when_not_completed(self, tenant_a, employee_a):
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=12)
        progress = LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=course)
        assert progress.certification_expires_on is None

    def test_certification_expires_on_none_when_course_not_certification(self, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import LearningProgress
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=training_course_a,
            completed_at=timezone.now(), status="completed",
        )
        assert progress.certification_expires_on is None  # training_course_a.is_certification is False

    def test_certification_expires_on_none_when_no_validity_months(self, tenant_a, employee_a):
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course No Validity", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=None)
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=course,
            completed_at=timezone.now(), status="completed",
        )
        assert progress.certification_expires_on is None

    def test_certification_expires_on_leap_year_month_math_clamp(self, tenant_a, employee_a):
        """completed 2024-01-31 + 1 month clamps to 2024-02-29 (2024 is a leap year)."""
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course Leap", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=1)
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=course,
            completed_at=_dt(2024, 1, 31, 12, 0), status="completed",
        )
        assert progress.certification_expires_on == datetime.date(2024, 2, 29)

    def test_certification_expires_on_non_leap_year_month_math_clamp(self, tenant_a, employee_a):
        """completed 2023-01-31 + 1 month clamps to 2023-02-28 (2023 is NOT a leap year)."""
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course Non-Leap", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=1)
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=course,
            completed_at=_dt(2023, 1, 31, 12, 0), status="completed",
        )
        assert progress.certification_expires_on == datetime.date(2023, 2, 28)

    def test_certification_expires_on_crosses_year_boundary(self, tenant_a, employee_a):
        """completed 2025-12-15 + 3 months -> 2026-03-15 (month math rolls over into the next year)."""
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course Rollover", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=3)
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=course,
            completed_at=_dt(2025, 12, 15, 12, 0), status="completed",
        )
        assert progress.certification_expires_on == datetime.date(2026, 3, 15)

    # -------------------------------------------------- derived: is_certification_expired
    def test_is_certification_expired_true_when_past(self, tenant_a, employee_a):
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course Expired", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=1)
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=course, status="completed",
            completed_at=timezone.now() - datetime.timedelta(days=400),
        )
        assert progress.is_certification_expired is True

    def test_is_certification_expired_false_when_future(self, tenant_a, employee_a):
        from apps.hrm.models import LearningProgress, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert Course Valid", is_certification=True,
            certification_name="Certified Thing", certification_validity_months=12)
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=course, status="completed",
            completed_at=timezone.now(),
        )
        assert progress.is_certification_expired is False

    def test_is_certification_expired_false_when_no_expiry(self, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import LearningProgress
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=training_course_a, status="completed",
            completed_at=timezone.now(),
        )
        assert progress.is_certification_expired is False  # non-certification course -> no expiry at all

    # -------------------------------------------------- FK on_delete behavior
    def test_progress_deleted_when_employee_deleted(self, tenant_a, employee_a, learning_progress_a):
        from apps.hrm.models import LearningProgress
        pk = learning_progress_a.pk
        employee_a.delete()
        assert not LearningProgress.objects.filter(pk=pk).exists()

    def test_course_delete_protected_when_progress_exists(self, learning_progress_a, training_course_a):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            training_course_a.delete()

    def test_learning_path_set_null_on_path_delete(self, tenant_a, employee_a, training_course_a, learning_path_a):
        from apps.hrm.models import LearningProgress
        progress = LearningProgress.objects.create(
            tenant=tenant_a, employee=employee_a, course=training_course_a, learning_path=learning_path_a)
        learning_path_a.delete()
        progress.refresh_from_db()
        assert progress.learning_path_id is None


# ================================================================ leaderboard level helper
class TestLmsLevelForPoints:
    @pytest.mark.parametrize("points,expected", [
        (0, "Bronze"),
        (1, "Bronze"),
        (149, "Bronze"),
        (150, "Silver"),
        (151, "Silver"),
        (399, "Silver"),
        (400, "Gold"),
        (401, "Gold"),
        (799, "Gold"),
        (800, "Platinum"),
        (5000, "Platinum"),
    ])
    def test_level_thresholds(self, points, expected):
        from apps.hrm.views import _lms_level_for_points
        assert _lms_level_for_points(points) == expected


# ================================================================ Forms — regression pins (review-caught bugs)
class TestLearningProgressFormDuplicateGuard:
    def _data(self, employee, course, **overrides):
        data = {
            "employee": employee.pk, "course": course.pk, "learning_path": "",
            "status": "not_started", "percent_complete": "0", "time_spent_minutes": "0",
            "score": "", "passed": "", "attempt_count": "0", "points_earned": "0",
            "started_at": "", "completed_at": "",
        }
        data.update(overrides)
        return data

    def test_duplicate_employee_course_pair_is_invalid(self, tenant_a, employee_a, training_course_a, learning_progress_a):
        from apps.hrm.forms import LearningProgressForm
        form = LearningProgressForm(self._data(employee_a, training_course_a), tenant=tenant_a)
        assert form.is_valid() is False

    def test_distinct_employee_course_pair_is_valid(self, tenant_a, employee_a2, training_course_a, learning_progress_a):
        from apps.hrm.forms import LearningProgressForm
        form = LearningProgressForm(self._data(employee_a2, training_course_a), tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_editing_own_record_does_not_collide_with_itself(self, tenant_a, employee_a, training_course_a, learning_progress_a):
        from apps.hrm.forms import LearningProgressForm
        form = LearningProgressForm(
            self._data(employee_a, training_course_a, status="in_progress"),
            instance=learning_progress_a, tenant=tenant_a,
        )
        assert form.is_valid() is True, form.errors


class TestLearningPathItemFormDuplicateGuard:
    def test_readding_same_course_to_path_is_invalid(self, tenant_a, learning_path_a, training_course_a, path_item_a):
        from apps.hrm.forms import LearningPathItemForm
        from apps.hrm.models import LearningPathItem
        data = {"course": training_course_a.pk, "sequence": "2", "is_mandatory": "on"}
        form = LearningPathItemForm(
            data, instance=LearningPathItem(tenant=tenant_a, path=learning_path_a), tenant=tenant_a)
        assert form.is_valid() is False

    def test_new_course_in_path_is_valid(self, tenant_a, learning_path_a, path_item_a):
        from apps.hrm.forms import LearningPathItemForm
        from apps.hrm.models import LearningPathItem, TrainingCourse
        other = TrainingCourse.objects.create(tenant=tenant_a, title="Second Course", is_active=True)
        data = {"course": other.pk, "sequence": "2", "is_mandatory": "on"}
        form = LearningPathItemForm(
            data, instance=LearningPathItem(tenant=tenant_a, path=learning_path_a), tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_editing_own_item_does_not_collide_with_itself(self, tenant_a, learning_path_a, training_course_a, path_item_a):
        from apps.hrm.forms import LearningPathItemForm
        data = {"course": training_course_a.pk, "sequence": "1", "is_mandatory": ""}
        form = LearningPathItemForm(data, instance=path_item_a, tenant=tenant_a)
        assert form.is_valid() is True, form.errors


# ================================================================ Forms — file upload validation
class TestLearningContentItemFormFileValidation:
    def _data(self, **overrides):
        data = {
            "title": "Lesson", "description": "", "content_type": "text", "sequence": "1",
            "is_required": "on", "estimated_duration_minutes": "", "video_url": "",
            "external_url": "", "body_text": "Some article content.",
            "pass_threshold_percent": "70", "max_attempts": "1", "time_limit_minutes": "",
        }
        data.update(overrides)
        return data

    def test_scorm_package_non_zip_rejected(self, tenant_a):
        from apps.hrm.forms import LearningContentItemForm
        files = {"scorm_package": SimpleUploadedFile(
            "package.rar", b"junk data", content_type="application/x-rar-compressed")}
        form = LearningContentItemForm(self._data(), files, tenant=tenant_a)
        assert form.is_valid() is False
        assert "scorm_package" in form.errors

    def test_scorm_package_zip_accepted(self, tenant_a, training_course_a):
        from apps.hrm.forms import LearningContentItemForm
        from apps.hrm.models import LearningContentItem
        files = {"scorm_package": SimpleUploadedFile(
            "package.zip", b"PK\x03\x04 test", content_type="application/zip")}
        form = LearningContentItemForm(
            self._data(content_type="scorm", body_text=""),
            files, instance=LearningContentItem(tenant=tenant_a, course=training_course_a), tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_document_file_disallowed_extension_rejected(self, tenant_a):
        from apps.hrm.forms import LearningContentItemForm
        files = {"document_file": SimpleUploadedFile(
            "malware.exe", b"junk data", content_type="application/octet-stream")}
        form = LearningContentItemForm(self._data(), files, tenant=tenant_a)
        assert form.is_valid() is False
        assert "document_file" in form.errors

    def test_document_file_allowed_extension_accepted(self, tenant_a, training_course_a):
        from apps.hrm.forms import LearningContentItemForm
        from apps.hrm.models import LearningContentItem
        files = {"document_file": SimpleUploadedFile(
            "notes.pdf", b"%PDF-1.4 test", content_type="application/pdf")}
        form = LearningContentItemForm(
            self._data(content_type="document", body_text=""),
            files, instance=LearningContentItem(tenant=tenant_a, course=training_course_a), tenant=tenant_a)
        assert form.is_valid() is True, form.errors


class TestLearningPathItemFormCourseQueryset:
    def test_course_queryset_limited_to_active_courses(self, tenant_a, training_course_a):
        from apps.hrm.forms import LearningPathItemForm
        from apps.hrm.models import TrainingCourse
        inactive = TrainingCourse.objects.create(tenant=tenant_a, title="Retired Course", is_active=False)
        form = LearningPathItemForm(tenant=tenant_a)
        pks = list(form.fields["course"].queryset.values_list("pk", flat=True))
        assert training_course_a.pk in pks
        assert inactive.pk not in pks

    def test_course_queryset_excludes_other_tenant_courses(self, tenant_a, tenant_b, training_course_b):
        from apps.hrm.forms import LearningPathItemForm
        form = LearningPathItemForm(tenant=tenant_a)
        pks = list(form.fields["course"].queryset.values_list("pk", flat=True))
        assert training_course_b.pk not in pks
