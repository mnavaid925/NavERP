"""Tests for HRM 3.24 Training Administration models: ``TrainingNomination`` (NOM-, per-tenant
sequence, clean() blocks nominating into a completed/cancelled session), ``TrainingAttendance``
(no number, clean() check_out>=check_in + nomination/session/employee-match guard),
``TrainingFeedback`` (no number, one-per-attendance, ``giver_anonymized`` mirrors ``is_anonymous``),
and ``TrainingCertificate`` (CERT-, ``save()`` mints a one-shot ``verification_code`` + a
title-from-course default + a RECOMPUTED-EVERY-SAVE ``expires_on`` — the review fix pinned below —
``is_expired`` derived off ``expires_on`` vs today, clean() single-source + source/employee/course
match guards). Also covers ``TrainingSession.approved_nomination_count``/``is_full`` (3.24
cross-touch) and the shared ``_advance_months`` month-math helper (leap/non-leap clamp + year
rollover), plus form-level regression pins for the three (tenant, ...)-excluded duplicate guards
that Django's ModelForm ``validate_unique()`` would otherwise skip (the 3.22/3.23 gotcha, reused
here) and the certification-only ``course`` queryset on ``TrainingCertificateForm``."""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError

pytestmark = pytest.mark.django_db


def _dt(y, m, d, h=0, mi=0):
    return datetime.datetime(y, m, d, h, mi, tzinfo=datetime.timezone.utc)


# ================================================================ TrainingNomination
class TestTrainingNominationModel:
    def test_number_prefix(self, nomination_a):
        assert nomination_a.number.startswith("NOM-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, training_session_a, employee_a, employee_a2):
        from apps.hrm.models import TrainingNomination
        n1 = TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a)
        n2 = TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2)
        assert n1.number != n2.number
        assert n1.number.startswith("NOM-")
        assert n2.number.startswith("NOM-")

    def test_unique_together_tenant_number(self, tenant_a, nomination_a):
        from apps.hrm.models import TrainingNomination
        with pytest.raises(IntegrityError):
            TrainingNomination.objects.create(
                tenant=tenant_a, number=nomination_a.number,
                session=nomination_a.session, employee=nomination_a.employee)

    def test_unique_together_tenant_session_employee(self, tenant_a, training_session_a, employee_a, nomination_a):
        from apps.hrm.models import TrainingNomination
        with pytest.raises(IntegrityError):
            TrainingNomination.objects.create(
                tenant=tenant_a, session=training_session_a, employee=employee_a)

    def test_default_status_pending(self, nomination_a):
        assert nomination_a.status == "pending"

    def test_default_nomination_type_self(self, nomination_a):
        assert nomination_a.nomination_type == "self"

    def test_default_priority_normal(self, nomination_a):
        assert nomination_a.priority == "normal"

    def test_default_approver_and_approved_at_none(self, nomination_a):
        assert nomination_a.approver_id is None
        assert nomination_a.approved_at is None

    def test_str_contains_number_employee_session(self, nomination_a):
        s = str(nomination_a)
        assert nomination_a.number in s
        assert "Alice Smith" in s

    def test_str_falls_back_to_employee_when_no_number(self, tenant_a, employee_a, training_session_a):
        from apps.hrm.models import TrainingNomination
        n = TrainingNomination(tenant=tenant_a, session=training_session_a, employee=employee_a)
        assert str(n) == str(employee_a)

    # -------------------------------------------------- clean(): session status gate
    def test_clean_completed_session_raises_on_session(self, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingNomination
        training_session_a.status = "completed"
        training_session_a.save(update_fields=["status"])
        n = TrainingNomination(tenant=tenant_a, session=training_session_a, employee=employee_a)
        with pytest.raises(ValidationError) as exc:
            n.clean()
        assert "session" in exc.value.message_dict

    def test_clean_cancelled_session_raises_on_session(self, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingNomination
        training_session_a.status = "cancelled"
        training_session_a.save(update_fields=["status"])
        n = TrainingNomination(tenant=tenant_a, session=training_session_a, employee=employee_a)
        with pytest.raises(ValidationError) as exc:
            n.clean()
        assert "session" in exc.value.message_dict

    @pytest.mark.parametrize("status", ["scheduled", "confirmed", "ongoing", "postponed"])
    def test_clean_active_session_status_valid(self, tenant_a, training_session_a, employee_a, status):
        from apps.hrm.models import TrainingNomination
        training_session_a.status = status
        training_session_a.save(update_fields=["status"])
        n = TrainingNomination(tenant=tenant_a, session=training_session_a, employee=employee_a)
        n.clean()  # must not raise

    # -------------------------------------------------- FK on_delete behavior
    def test_session_delete_protected_when_nomination_exists(self, nomination_a, training_session_a):
        with pytest.raises(ProtectedError):
            training_session_a.delete()

    def test_employee_delete_protected_when_nomination_exists(self, nomination_a, employee_a):
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_nominated_by_set_null_on_delete(self, tenant_a, training_session_a, employee_a, employee_a2):
        from apps.hrm.models import TrainingNomination
        n = TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a, nominated_by=employee_a2)
        employee_a2.delete()
        n.refresh_from_db()
        assert n.nominated_by_id is None


# ================================================================ TrainingAttendance
class TestTrainingAttendanceModel:
    def test_no_number_field(self, training_attendance_a):
        assert not hasattr(training_attendance_a, "number")

    def test_default_completion_status_not_completed(self, training_attendance_a):
        assert training_attendance_a.completion_status == "not_completed"

    def test_unique_together_tenant_session_employee(self, tenant_a, training_session_a, employee_a, training_attendance_a):
        from apps.hrm.models import TrainingAttendance
        with pytest.raises(IntegrityError):
            TrainingAttendance.objects.create(
                tenant=tenant_a, session=training_session_a, employee=employee_a)

    def test_str_contains_employee_session_and_status_display(self, training_attendance_a):
        s = str(training_attendance_a)
        assert "Alice Smith" in s
        assert "Present" in s

    # -------------------------------------------------- clean(): check_out >= check_in
    def test_clean_check_out_before_check_in_raises(self, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance(
            tenant=tenant_a, session=training_session_a, employee=employee_a,
            check_in_at=_dt(2026, 7, 20, 10, 0), check_out_at=_dt(2026, 7, 20, 9, 0))
        with pytest.raises(ValidationError) as exc:
            att.clean()
        assert "check_out_at" in exc.value.message_dict

    def test_clean_check_out_after_check_in_valid(self, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance(
            tenant=tenant_a, session=training_session_a, employee=employee_a,
            check_in_at=_dt(2026, 7, 20, 9, 0), check_out_at=_dt(2026, 7, 20, 17, 0))
        att.clean()  # must not raise

    def test_clean_no_times_valid(self, training_attendance_a):
        training_attendance_a.clean()  # must not raise — neither check_in_at nor check_out_at set

    # -------------------------------------------------- clean(): nomination session/employee match
    def test_clean_nomination_employee_mismatch_raises(self, tenant_a, training_session_a, employee_a, employee_a2, nomination_a):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance(
            tenant=tenant_a, session=training_session_a, employee=employee_a2, nomination=nomination_a)
        with pytest.raises(ValidationError) as exc:
            att.clean()
        assert "nomination" in exc.value.message_dict

    def test_clean_nomination_session_mismatch_raises(self, tenant_a, tenant_b, employee_a, nomination_a):
        """nomination_a is scoped to training_session_a; a different session on the attendance mismatches."""
        from apps.hrm.models import TrainingAttendance, TrainingCourse, TrainingSession
        other_course = TrainingCourse.objects.create(tenant=nomination_a.tenant, title="Other Course")
        other_session = TrainingSession.objects.create(
            tenant=nomination_a.tenant, course=other_course, delivery_mode="classroom",
            start_datetime=_dt(2026, 8, 1, 9, 0), end_datetime=_dt(2026, 8, 1, 17, 0),
            venue_name="Room 202",
        )
        att = TrainingAttendance(
            tenant=nomination_a.tenant, session=other_session, employee=nomination_a.employee,
            nomination=nomination_a)
        with pytest.raises(ValidationError) as exc:
            att.clean()
        assert "nomination" in exc.value.message_dict

    def test_clean_matching_nomination_valid(self, tenant_a, training_session_a, employee_a, nomination_a):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance(
            tenant=tenant_a, session=training_session_a, employee=employee_a, nomination=nomination_a)
        att.clean()  # must not raise — same session + same employee

    def test_clean_no_nomination_valid(self, training_attendance_a):
        training_attendance_a.clean()  # must not raise — walk-in, no nomination link

    # -------------------------------------------------- FK on_delete behavior
    def test_session_delete_protected_when_attendance_exists(self, training_attendance_a, training_session_a):
        with pytest.raises(ProtectedError):
            training_session_a.delete()

    def test_employee_delete_protected_when_attendance_exists(self, training_attendance_a, employee_a):
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_nomination_set_null_on_delete(self, tenant_a, training_session_a, employee_a, nomination_a):
        from apps.hrm.models import TrainingAttendance
        att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a, nomination=nomination_a)
        nomination_a.delete()
        att.refresh_from_db()
        assert att.nomination_id is None


# ================================================================ TrainingFeedback
class TestTrainingFeedbackModel:
    def test_no_number_field(self, training_feedback_a):
        assert not hasattr(training_feedback_a, "number")

    def test_default_is_anonymous_false(self, training_feedback_a):
        assert training_feedback_a.is_anonymous is False

    def test_default_would_recommend_true(self, training_feedback_a):
        assert training_feedback_a.would_recommend is True

    def test_unique_together_tenant_attendance(self, tenant_a, training_attendance_a, training_feedback_a):
        from apps.hrm.models import TrainingFeedback
        with pytest.raises(IntegrityError):
            TrainingFeedback.objects.create(
                tenant=tenant_a, attendance=training_attendance_a,
                overall_rating=3, content_rating=3, trainer_rating=3)

    def test_giver_anonymized_mirrors_is_anonymous_false(self, training_feedback_a):
        assert training_feedback_a.giver_anonymized is False

    def test_giver_anonymized_mirrors_is_anonymous_true(self, training_feedback_a):
        training_feedback_a.is_anonymous = True
        training_feedback_a.save(update_fields=["is_anonymous"])
        assert training_feedback_a.giver_anonymized is True

    def test_str_contains_attendance(self, training_feedback_a):
        s = str(training_feedback_a)
        assert "Feedback" in s

    def test_str_falls_back_when_no_attendance(self, tenant_a):
        from apps.hrm.models import TrainingFeedback
        fb = TrainingFeedback(tenant=tenant_a)
        assert str(fb) == "Feedback"

    # -------------------------------------------------- rating validators (model-level)
    @pytest.mark.parametrize("rating", [0, 6])
    def test_overall_rating_outside_range_rejected_by_full_clean(self, tenant_a, training_attendance_a, rating):
        from apps.hrm.models import TrainingFeedback
        fb = TrainingFeedback(
            tenant=tenant_a, attendance=training_attendance_a,
            overall_rating=rating, content_rating=3, trainer_rating=3)
        with pytest.raises(ValidationError):
            fb.full_clean()

    # -------------------------------------------------- FK on_delete behavior
    def test_feedback_deleted_when_attendance_deleted(self, tenant_a, training_attendance_a, training_feedback_a):
        from apps.hrm.models import TrainingFeedback
        pk = training_feedback_a.pk
        training_attendance_a.delete()
        assert not TrainingFeedback.objects.filter(pk=pk).exists()


# ================================================================ TrainingCertificate
class TestTrainingCertificateModel:
    def test_number_prefix(self, training_certificate_a):
        assert training_certificate_a.number.startswith("CERT-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        c1 = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a, course=cert_course_a)
        c2 = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a2, course=cert_course_a)
        assert c1.number != c2.number
        assert c1.number.startswith("CERT-")
        assert c2.number.startswith("CERT-")

    def test_unique_together_tenant_number(self, tenant_a, training_certificate_a):
        from apps.hrm.models import TrainingCertificate
        with pytest.raises(IntegrityError):
            TrainingCertificate.objects.create(
                tenant=tenant_a, number=training_certificate_a.number,
                employee=training_certificate_a.employee, course=training_certificate_a.course)

    def test_default_status_issued(self, training_certificate_a):
        assert training_certificate_a.status == "issued"

    # -------------------------------------------------- save(): verification_code
    def test_verification_code_generated_16_hex_chars(self, training_certificate_a):
        import re
        assert re.fullmatch(r"[0-9A-F]{16}", training_certificate_a.verification_code)

    def test_verification_code_not_regenerated_on_resave(self, training_certificate_a):
        original = training_certificate_a.verification_code
        training_certificate_a.revoked_reason = "no-op edit"
        training_certificate_a.save()
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.verification_code == original

    def test_verification_code_unique_across_tenants(self, training_certificate_a, tenant_b, employee_b, cert_course_b):
        """verification_code has no tenant scoping (global unique=True) — distinct certs across
        different tenants still get distinct codes."""
        from apps.hrm.models import TrainingCertificate
        other = TrainingCertificate.objects.create(tenant=tenant_b, employee=employee_b, course=cert_course_b)
        assert other.verification_code != training_certificate_a.verification_code

    # -------------------------------------------------- save(): title default
    def test_title_defaults_from_course_certification_name(self, training_certificate_a, cert_course_a):
        assert training_certificate_a.title == cert_course_a.certification_name == "Safety Certification"

    def test_title_falls_back_to_course_title_when_certification_name_blank(self, tenant_a, employee_a, training_course_a):
        """training_course_a is non-certification (certification_name blank) — title falls back to
        course.title even though the form normally restricts course selection to is_certification."""
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a, course=training_course_a)
        assert cert.title == training_course_a.title == "Advanced Python"

    def test_explicit_title_not_overwritten(self, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, title="Custom Title")
        assert cert.title == "Custom Title"

    # -------------------------------------------------- save(): expires_on computed + RECOMPUTED (review fix)
    def test_expires_on_computed_from_issued_on_plus_validity(self, training_certificate_a):
        assert training_certificate_a.expires_on == datetime.date(2027, 7, 1)

    def test_expires_on_none_when_course_not_certification(self, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a, course=training_course_a)
        assert cert.expires_on is None

    def test_expires_on_none_when_no_validity_months(self, tenant_a, employee_a):
        from apps.hrm.models import TrainingCertificate, TrainingCourse
        course = TrainingCourse.objects.create(
            tenant=tenant_a, title="Cert No Validity", is_certification=True,
            certification_name="Cert No Validity Cert", certification_validity_months=None)
        cert = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a, course=course)
        assert cert.expires_on is None

    def test_expires_on_recomputes_when_issued_on_changes(self, training_certificate_a):
        """Regression pin (review fix): editing issued_on and re-saving MUST move expires_on too —
        expires_on is NOT frozen from the first save."""
        assert training_certificate_a.expires_on == datetime.date(2027, 7, 1)
        training_certificate_a.issued_on = datetime.date(2026, 8, 1)
        training_certificate_a.save()
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.expires_on == datetime.date(2027, 8, 1)

    def test_expires_on_cleared_if_course_swapped_to_non_certification(
        self, training_certificate_a, training_course_a
    ):
        """Recomputing on every save also means swapping the linked course to a non-certification
        one clears a previously-computed expires_on."""
        assert training_certificate_a.expires_on is not None
        training_certificate_a.course = training_course_a
        training_certificate_a.save()
        training_certificate_a.refresh_from_db()
        assert training_certificate_a.expires_on is None

    # -------------------------------------------------- is_expired (derived)
    def test_is_expired_true_when_past(self, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(
            tenant=tenant_a, employee=employee_a, course=cert_course_a,
            issued_on=datetime.date(2020, 1, 1))
        assert cert.is_expired is True

    def test_is_expired_false_when_future(self, training_certificate_a):
        assert training_certificate_a.is_expired is False  # issued 2026-07-01, expires 2027-07-01

    def test_is_expired_false_when_no_expiry(self, tenant_a, employee_a, training_course_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a, course=training_course_a)
        assert cert.is_expired is False

    # -------------------------------------------------- clean(): single-source + match guards
    def test_clean_both_sources_set_raises(self, tenant_a, employee_a, cert_course_a, training_attendance_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=cert_course_a)
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a, course=cert_course_a,
            source_attendance=training_attendance_a, source_progress=progress)
        with pytest.raises(ValidationError) as exc:
            cert.clean()
        assert "source_progress" in exc.value.message_dict

    def test_clean_source_attendance_employee_mismatch_raises(
        self, tenant_a, employee_a2, cert_course_a, training_attendance_a
    ):
        """training_attendance_a belongs to employee_a; a cert for employee_a2 mismatches."""
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a2, course=cert_course_a,
            source_attendance=training_attendance_a)
        with pytest.raises(ValidationError) as exc:
            cert.clean()
        assert "source_attendance" in exc.value.message_dict

    def test_clean_source_attendance_course_mismatch_raises(self, tenant_a, employee_a, cert_course_a, training_attendance_a):
        """training_attendance_a's session is on training_course_a; a cert for cert_course_a mismatches."""
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a, course=cert_course_a,
            source_attendance=training_attendance_a)
        with pytest.raises(ValidationError) as exc:
            cert.clean()
        assert "source_attendance" in exc.value.message_dict

    def test_clean_source_attendance_matching_valid(self, tenant_a, employee_a, training_course_a, training_attendance_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a, course=training_course_a,
            source_attendance=training_attendance_a)
        cert.clean()  # must not raise — same employee + same course (via session)

    def test_clean_source_progress_employee_mismatch_raises(self, tenant_a, employee_a, employee_a2, cert_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=cert_course_a)
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a2, course=cert_course_a, source_progress=progress)
        with pytest.raises(ValidationError) as exc:
            cert.clean()
        assert "source_progress" in exc.value.message_dict

    def test_clean_source_progress_course_mismatch_raises(self, tenant_a, employee_a, cert_course_a, training_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=training_course_a)
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, source_progress=progress)
        with pytest.raises(ValidationError) as exc:
            cert.clean()
        assert "source_progress" in exc.value.message_dict

    def test_clean_source_progress_matching_valid(self, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=cert_course_a)
        cert = TrainingCertificate(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, source_progress=progress)
        cert.clean()  # must not raise

    def test_clean_no_source_valid(self, training_certificate_a):
        training_certificate_a.clean()  # must not raise — manually issued, no source link

    def test_str_contains_number_employee_title(self, training_certificate_a):
        s = str(training_certificate_a)
        assert training_certificate_a.number in s
        assert "Alice Smith" in s
        assert "Safety Certification" in s

    def test_str_falls_back_to_title_when_no_number(self, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate(tenant=tenant_a, employee=employee_a, course=cert_course_a, title="Draft Cert")
        assert str(cert) == "Draft Cert"

    # -------------------------------------------------- FK on_delete behavior
    def test_employee_delete_protected_when_certificate_exists(self, training_certificate_a, employee_a):
        with pytest.raises(ProtectedError):
            employee_a.delete()

    def test_course_delete_protected_when_certificate_exists(self, training_certificate_a, cert_course_a):
        with pytest.raises(ProtectedError):
            cert_course_a.delete()

    def test_source_attendance_set_null_on_delete(self, tenant_a, employee_a, training_course_a, training_attendance_a):
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(
            tenant=tenant_a, employee=employee_a, course=training_course_a,
            source_attendance=training_attendance_a)
        training_attendance_a.delete()
        cert.refresh_from_db()
        assert cert.source_attendance_id is None

    def test_source_progress_set_null_on_delete(self, tenant_a, employee_a, cert_course_a):
        from apps.hrm.models import LearningProgress, TrainingCertificate
        progress = LearningProgress.objects.create(tenant=tenant_a, employee=employee_a, course=cert_course_a)
        cert = TrainingCertificate.objects.create(
            tenant=tenant_a, employee=employee_a, course=cert_course_a, source_progress=progress)
        progress.delete()
        cert.refresh_from_db()
        assert cert.source_progress_id is None


# ================================================================ TrainingSession cross-touch (3.24)
class TestTrainingSessionNominationCrossTouch:
    def test_approved_nomination_count_zero_by_default(self, training_session_a):
        assert training_session_a.approved_nomination_count == 0

    def test_approved_nomination_count_only_counts_approved(self, tenant_a, training_session_a, employee_a, employee_a2):
        from apps.hrm.models import TrainingNomination
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a, status="approved")
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2, status="pending")
        assert training_session_a.approved_nomination_count == 1

    def test_is_full_false_below_capacity(self, tenant_a, training_session_a, employee_a):
        from apps.hrm.models import TrainingNomination
        training_session_a.capacity = 2
        training_session_a.save(update_fields=["capacity"])
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a, status="approved")
        assert training_session_a.is_full is False

    def test_is_full_true_at_capacity(self, tenant_a, training_session_a, employee_a, employee_a2):
        from apps.hrm.models import TrainingNomination
        training_session_a.capacity = 2
        training_session_a.save(update_fields=["capacity"])
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a, status="approved")
        TrainingNomination.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2, status="approved")
        assert training_session_a.is_full is True


# ================================================================ shared _advance_months helper
class TestAdvanceMonths:
    def test_leap_year_month_math_clamp(self):
        from apps.hrm.models import _advance_months
        assert _advance_months(datetime.date(2024, 1, 31), 1) == datetime.date(2024, 2, 29)

    def test_non_leap_year_month_math_clamp(self):
        from apps.hrm.models import _advance_months
        assert _advance_months(datetime.date(2023, 1, 31), 1) == datetime.date(2023, 2, 28)

    def test_year_rollover(self):
        from apps.hrm.models import _advance_months
        assert _advance_months(datetime.date(2025, 12, 15), 3) == datetime.date(2026, 3, 15)

    def test_zero_months_is_identity(self):
        from apps.hrm.models import _advance_months
        assert _advance_months(datetime.date(2026, 7, 10), 0) == datetime.date(2026, 7, 10)


# ================================================================ Forms — regression pins (duplicate guards)
class TestTrainingNominationFormDuplicateGuard:
    def _data(self, session, employee, **overrides):
        data = {
            "session": session.pk, "employee": employee.pk, "nominated_by": "",
            "nomination_type": "self", "justification": "", "priority": "normal",
        }
        data.update(overrides)
        return data

    def test_duplicate_session_employee_pair_is_invalid(self, tenant_a, training_session_a, employee_a, nomination_a):
        from apps.hrm.forms import TrainingNominationForm
        form = TrainingNominationForm(self._data(training_session_a, employee_a), tenant=tenant_a)
        assert form.is_valid() is False

    def test_distinct_employee_is_valid(self, tenant_a, training_session_a, employee_a2, nomination_a):
        from apps.hrm.forms import TrainingNominationForm
        form = TrainingNominationForm(self._data(training_session_a, employee_a2), tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_editing_own_record_does_not_collide_with_itself(self, tenant_a, training_session_a, employee_a, nomination_a):
        from apps.hrm.forms import TrainingNominationForm
        form = TrainingNominationForm(
            self._data(training_session_a, employee_a, priority="high"),
            instance=nomination_a, tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_session_queryset_excludes_cancelled_and_postponed(self, tenant_a, training_session_a):
        from apps.hrm.forms import TrainingNominationForm
        training_session_a.status = "cancelled"
        training_session_a.save(update_fields=["status"])
        form = TrainingNominationForm(tenant=tenant_a)
        pks = list(form.fields["session"].queryset.values_list("pk", flat=True))
        assert training_session_a.pk not in pks


class TestTrainingAttendanceFormDuplicateGuard:
    def _data(self, session, employee, **overrides):
        data = {
            "session": session.pk, "employee": employee.pk, "nomination": "",
            "attendance_status": "registered", "completion_status": "not_completed",
            "check_in_at": "", "check_out_at": "", "notes": "",
        }
        data.update(overrides)
        return data

    def test_duplicate_session_employee_pair_is_invalid(self, tenant_a, training_session_a, employee_a, training_attendance_a):
        from apps.hrm.forms import TrainingAttendanceForm
        form = TrainingAttendanceForm(self._data(training_session_a, employee_a), tenant=tenant_a)
        assert form.is_valid() is False

    def test_distinct_employee_is_valid(self, tenant_a, training_session_a, employee_a2, training_attendance_a):
        from apps.hrm.forms import TrainingAttendanceForm
        form = TrainingAttendanceForm(self._data(training_session_a, employee_a2), tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_editing_own_record_does_not_collide_with_itself(self, tenant_a, training_session_a, employee_a, training_attendance_a):
        from apps.hrm.forms import TrainingAttendanceForm
        form = TrainingAttendanceForm(
            self._data(training_session_a, employee_a, attendance_status="present"),
            instance=training_attendance_a, tenant=tenant_a)
        assert form.is_valid() is True, form.errors


class TestTrainingFeedbackFormDuplicateGuard:
    def _data(self, **overrides):
        data = {
            "overall_rating": "5", "content_rating": "4", "trainer_rating": "5",
            "would_recommend": "on", "comments": "", "is_anonymous": "",
        }
        data.update(overrides)
        return data

    def test_duplicate_attendance_is_invalid(self, tenant_a, training_attendance_a, training_feedback_a):
        from apps.hrm.forms import TrainingFeedbackForm
        from apps.hrm.models import TrainingFeedback
        form = TrainingFeedbackForm(
            self._data(), instance=TrainingFeedback(tenant=tenant_a, attendance=training_attendance_a),
            tenant=tenant_a)
        assert form.is_valid() is False

    def test_new_attendance_is_valid(self, tenant_a, training_session_a, employee_a2):
        from apps.hrm.forms import TrainingFeedbackForm
        from apps.hrm.models import TrainingAttendance, TrainingFeedback
        other_att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2)
        form = TrainingFeedbackForm(
            self._data(), instance=TrainingFeedback(tenant=tenant_a, attendance=other_att), tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_editing_own_feedback_does_not_collide_with_itself(self, tenant_a, training_feedback_a):
        from apps.hrm.forms import TrainingFeedbackForm
        form = TrainingFeedbackForm(self._data(comments="Updated"), instance=training_feedback_a, tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    @pytest.mark.parametrize("rating", ["0", "6"])
    def test_rating_outside_1_5_rejected(self, tenant_a, training_session_a, employee_a2, rating):
        from apps.hrm.forms import TrainingFeedbackForm
        from apps.hrm.models import TrainingAttendance, TrainingFeedback
        other_att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2)
        form = TrainingFeedbackForm(
            self._data(overall_rating=rating),
            instance=TrainingFeedback(tenant=tenant_a, attendance=other_att), tenant=tenant_a)
        assert form.is_valid() is False
        assert "overall_rating" in form.errors

    @pytest.mark.parametrize("rating", ["1", "5"])
    def test_rating_within_1_5_accepted(self, tenant_a, training_session_a, employee_a2, rating):
        from apps.hrm.forms import TrainingFeedbackForm
        from apps.hrm.models import TrainingAttendance, TrainingFeedback
        other_att = TrainingAttendance.objects.create(
            tenant=tenant_a, session=training_session_a, employee=employee_a2)
        form = TrainingFeedbackForm(
            self._data(overall_rating=rating),
            instance=TrainingFeedback(tenant=tenant_a, attendance=other_att), tenant=tenant_a)
        assert form.is_valid() is True, form.errors


class TestTrainingCertificateFormCourseQueryset:
    def test_course_queryset_limited_to_certification_courses(self, tenant_a, cert_course_a, training_course_a):
        from apps.hrm.forms import TrainingCertificateForm
        form = TrainingCertificateForm(tenant=tenant_a)
        pks = list(form.fields["course"].queryset.values_list("pk", flat=True))
        assert cert_course_a.pk in pks
        assert training_course_a.pk not in pks  # non-certification

    def test_course_queryset_keeps_already_linked_non_certification_course_on_edit(
        self, tenant_a, employee_a, training_course_a
    ):
        """A cert whose course was already linked (e.g. manually via a data fixture) before the
        course lost/never had is_certification must stay selectable when editing that cert."""
        from apps.hrm.forms import TrainingCertificateForm
        from apps.hrm.models import TrainingCertificate
        cert = TrainingCertificate.objects.create(tenant=tenant_a, employee=employee_a, course=training_course_a)
        form = TrainingCertificateForm(instance=cert, tenant=tenant_a)
        pks = list(form.fields["course"].queryset.values_list("pk", flat=True))
        assert training_course_a.pk in pks

    def test_course_queryset_excludes_other_tenant_courses(self, tenant_a, cert_course_b):
        from apps.hrm.forms import TrainingCertificateForm
        form = TrainingCertificateForm(tenant=tenant_a)
        pks = list(form.fields["course"].queryset.values_list("pk", flat=True))
        assert cert_course_b.pk not in pks
