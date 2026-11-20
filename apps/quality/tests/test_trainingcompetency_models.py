"""Unit tests for Quality Management Sub-module 12.12: Training & Competency Management models.

Tests models:
- CompetencyMatrix (prefix QMTX)
- QualityTrainingCourse (prefix QCRS)
- TrainingEnrollment (prefix QENR)
- CompetencyCertification (prefix QCERT)
"""
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import pytest
from django.conf import settings
from django.db import IntegrityError, models
from django.utils import timezone

from apps.quality.models import (
    CompetencyMatrix,
    QualityTrainingCourse,
    TrainingEnrollment,
    CompetencyCertification,
)


def _trainingcompetency_make_date(days_offset: int) -> date:
    """Helper to generate dates relative to today."""
    return timezone.now().date() + timedelta(days=days_offset)


# ============================================================================
# 1. CompetencyMatrix Model Tests (QMTX)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_creation_and_autonumber(competency_matrix_a, tenant_a, admin_user, quality_department):
    """Verify CompetencyMatrix creation, QMTX prefix, defaults, and field assignments."""
    assert competency_matrix_a.pk is not None
    assert competency_matrix_a.number.startswith("QMTX-")
    assert competency_matrix_a.tenant == tenant_a
    assert competency_matrix_a.role_title == "Cleanroom Technician"
    assert competency_matrix_a.department == quality_department
    assert competency_matrix_a.minimum_passing_score == 80
    assert competency_matrix_a.validity_period_months == 12
    assert competency_matrix_a.prerequisite_experience_months == 6
    assert competency_matrix_a.approved_by == admin_user
    assert competency_matrix_a.approval_date is not None


@pytest.mark.django_db
def test_trainingcompetency_matrix_str(competency_matrix_a):
    """Verify CompetencyMatrix __str__ format: {number} - {title} (v{revision})."""
    expected = f"{competency_matrix_a.number} - {competency_matrix_a.title} (v{competency_matrix_a.revision})"
    assert str(competency_matrix_a) == expected


@pytest.mark.django_db
def test_trainingcompetency_matrix_choices_and_badges(competency_matrix_a):
    """Verify tier_badge, criticality_badge, and status_badge mappings for CompetencyMatrix."""
    # Qualification tier badges
    for tier, expected_badge in CompetencyMatrix.QUALIFICATION_TIER_CSS.items():
        competency_matrix_a.qualification_tier = tier
        assert competency_matrix_a.tier_badge == expected_badge
    competency_matrix_a.qualification_tier = "unknown_tier"
    assert competency_matrix_a.tier_badge == "badge-slate"

    # Criticality badges
    for crit, expected_badge in CompetencyMatrix.CRITICALITY_CSS.items():
        competency_matrix_a.criticality = crit
        assert competency_matrix_a.criticality_badge == expected_badge
    competency_matrix_a.criticality = "unknown_criticality"
    assert competency_matrix_a.criticality_badge == "badge-slate"

    # Status badges
    for status, expected_badge in CompetencyMatrix.STATUS_CSS.items():
        competency_matrix_a.status = status
        assert competency_matrix_a.status_badge == expected_badge
    competency_matrix_a.status = "unknown_status"
    assert competency_matrix_a.status_badge == "badge-slate"


@pytest.mark.django_db
def test_trainingcompetency_matrix_counts_properties(competency_matrix_a, quality_course_a, competency_certification_a, tenant_a):
    """Verify courses_count, active_courses_count, and certifications_count on CompetencyMatrix."""
    # Baseline checks from fixtures
    assert competency_matrix_a.courses_count >= 1
    assert competency_matrix_a.active_courses_count >= 1
    assert competency_matrix_a.certifications_count >= 1

    # Add a draft course linked to the matrix
    QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="Draft Auxiliary Training",
        category="general",
        delivery_method="classroom_lecture",
        assessment_method="written_exam",
        status="draft",
        passing_score=75,
    )
    assert competency_matrix_a.courses_count == 2
    assert competency_matrix_a.active_courses_count == 1  # Only 1 is active

    # Add a revoked certification linked to the matrix
    CompetencyCertification.objects.create(
        tenant=tenant_a,
        trainee=competency_certification_a.trainee,
        course=quality_course_a,
        competency_matrix=competency_matrix_a,
        qualification_title="Revoked Qualification",
        qualification_level="level_1_novice",
        issue_date=_trainingcompetency_make_date(-60),
        valid_until=_trainingcompetency_make_date(300),
        renewal_interval_months=12,
        status="revoked",
        certified_by=competency_certification_a.certified_by,
    )
    # Only active certifications counted in certifications_count
    assert competency_matrix_a.certifications_count == 1


@pytest.mark.django_db
def test_trainingcompetency_matrix_unique_constraint(competency_matrix_a, tenant_a):
    """Verify database unique constraint on (tenant, number) for CompetencyMatrix."""
    with pytest.raises(IntegrityError):
        CompetencyMatrix.objects.create(
            tenant=tenant_a,
            number=competency_matrix_a.number,
            title="Duplicate Number Matrix",
            role_title="Cleanroom Technician",
        )


# ============================================================================
# 2. QualityTrainingCourse Model Tests (QCRS)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_course_creation_and_defaults(tenant_a, competency_matrix_a):
    """Verify QualityTrainingCourse creation, QCRS prefix, defaults (passing_score=80, duration=1.00)."""
    course = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="Gowning Protocol Baseline",
    )
    assert course.pk is not None
    assert course.number.startswith("QCRS-")
    assert course.category == "technical_sop"
    assert course.delivery_method == "read_and_understand"
    assert course.assessment_method == "written_exam"
    assert course.status == "draft"
    assert course.passing_score == 80
    assert course.duration_hours == Decimal("1.00")
    assert course.retrain_on_revision is True
    assert course.competency_matrix == competency_matrix_a


@pytest.mark.django_db
def test_trainingcompetency_course_str(quality_course_a):
    """Verify QualityTrainingCourse __str__ format: {number} - {title}."""
    expected = f"{quality_course_a.number} - {quality_course_a.title}"
    assert str(quality_course_a) == expected


@pytest.mark.django_db
def test_trainingcompetency_course_choices_and_badges(quality_course_a):
    """Verify badge properties for QualityTrainingCourse categories, methods, and status."""
    # Category badges
    for cat, expected_badge in QualityTrainingCourse.CATEGORY_CSS.items():
        quality_course_a.category = cat
        assert quality_course_a.category_badge == expected_badge
    quality_course_a.category = "unknown_cat"
    assert quality_course_a.category_badge == "badge-slate"

    # Delivery badges
    for method, expected_badge in QualityTrainingCourse.DELIVERY_METHOD_CSS.items():
        quality_course_a.delivery_method = method
        assert quality_course_a.delivery_badge == expected_badge
    quality_course_a.delivery_method = "unknown_delivery"
    assert quality_course_a.delivery_badge == "badge-slate"

    # Assessment badges
    for assess, expected_badge in QualityTrainingCourse.ASSESSMENT_METHOD_CSS.items():
        quality_course_a.assessment_method = assess
        assert quality_course_a.assessment_badge == expected_badge
    quality_course_a.assessment_method = "unknown_assessment"
    assert quality_course_a.assessment_badge == "badge-slate"

    # Status badges
    for status, expected_badge in QualityTrainingCourse.STATUS_CSS.items():
        quality_course_a.status = status
        assert quality_course_a.status_badge == expected_badge
    quality_course_a.status = "unknown_status"
    assert quality_course_a.status_badge == "badge-slate"


@pytest.mark.django_db
def test_trainingcompetency_course_enrollments_count_properties(quality_course_a, tenant_a, admin_user):
    """Verify enrollments_count, active_enrollments_count, and completed_enrollments_count."""
    today = timezone.now().date()
    # Create enrollments with various statuses
    e1 = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assigned_date=today - timedelta(days=10),
        due_date=today + timedelta(days=10),
        status="assigned",
    )
    e2 = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assigned_date=today - timedelta(days=10),
        due_date=today + timedelta(days=10),
        status="in_progress",
    )
    e3 = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assigned_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        status="completed",
    )
    e4 = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assigned_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        status="verified",
    )
    e5 = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assigned_date=today - timedelta(days=30),
        due_date=today - timedelta(days=10),
        status="waived",
    )

    # Active: assigned + in_progress (e1, e2)
    # Completed: completed + verified (e3, e4)
    # Total count: e1 + e2 + e3 + e4 + e5 (+ any from fixtures)
    assert quality_course_a.active_enrollments_count >= 2
    assert quality_course_a.completed_enrollments_count >= 2
    assert quality_course_a.enrollments_count >= 5


@pytest.mark.django_db
def test_trainingcompetency_course_unique_constraint(quality_course_a, tenant_a):
    """Verify database unique constraint on (tenant, number) for QualityTrainingCourse."""
    with pytest.raises(IntegrityError):
        QualityTrainingCourse.objects.create(
            tenant=tenant_a,
            number=quality_course_a.number,
            title="Duplicate Course Number",
        )


# ============================================================================
# 3. TrainingEnrollment Model Tests (QENR)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_enrollment_creation_and_defaults(training_enrollment_a, tenant_a, quality_course_a, admin_user):
    """Verify TrainingEnrollment creation, QENR prefix, defaults, and relationships."""
    assert training_enrollment_a.pk is not None
    assert training_enrollment_a.number.startswith("QENR-")
    assert training_enrollment_a.tenant == tenant_a
    assert training_enrollment_a.course == quality_course_a
    assert training_enrollment_a.trainee == admin_user
    assert training_enrollment_a.status == "assigned"
    assert training_enrollment_a.is_passed is False
    assert training_enrollment_a.self_certified is False


@pytest.mark.django_db
def test_trainingcompetency_enrollment_str(training_enrollment_a):
    """Verify TrainingEnrollment __str__ format: {number} - {course.title} ({trainee.username})."""
    expected = f"{training_enrollment_a.number} - {training_enrollment_a.course.title} ({training_enrollment_a.trainee.username})"
    assert str(training_enrollment_a) == expected


@pytest.mark.django_db
def test_trainingcompetency_enrollment_is_overdue(training_enrollment_a):
    """Verify is_overdue property behaves correctly across statuses and due dates."""
    today = timezone.now().date()

    # In assigned status with past due_date -> Overdue True
    training_enrollment_a.status = "assigned"
    training_enrollment_a.due_date = today - timedelta(days=1)
    assert training_enrollment_a.is_overdue is True

    # In in_progress status with past due_date -> Overdue True
    training_enrollment_a.status = "in_progress"
    training_enrollment_a.due_date = today - timedelta(days=5)
    assert training_enrollment_a.is_overdue is True

    # Future due date -> Overdue False
    training_enrollment_a.due_date = today + timedelta(days=10)
    assert training_enrollment_a.is_overdue is False

    # Today due date -> Overdue False
    training_enrollment_a.due_date = today
    assert training_enrollment_a.is_overdue is False

    # Completed, verified, waived, or failed even with past due_date -> Overdue False
    training_enrollment_a.due_date = today - timedelta(days=5)
    for terminal_status in ["completed", "verified", "waived", "failed", "overdue"]:
        training_enrollment_a.status = terminal_status
        assert training_enrollment_a.is_overdue is False


@pytest.mark.django_db
def test_trainingcompetency_enrollment_days_remaining(training_enrollment_a):
    """Verify days_remaining calculation."""
    today = timezone.now().date()
    training_enrollment_a.due_date = today + timedelta(days=15)
    assert training_enrollment_a.days_remaining == 15

    training_enrollment_a.due_date = today - timedelta(days=4)
    assert training_enrollment_a.days_remaining == -4

    training_enrollment_a.due_date = None
    assert training_enrollment_a.days_remaining == 0


@pytest.mark.django_db
def test_trainingcompetency_enrollment_requires_practical_verification(training_enrollment_a, quality_course_a):
    """Verify requires_practical_verification based on course assessment method and verification date."""
    # When course requires practical_ojt or both_exam_and_ojt and not verified -> True
    quality_course_a.assessment_method = "both_exam_and_ojt"
    quality_course_a.save()
    training_enrollment_a.practical_verified_at = None
    assert training_enrollment_a.requires_practical_verification is True

    quality_course_a.assessment_method = "practical_ojt"
    quality_course_a.save()
    assert training_enrollment_a.requires_practical_verification is True

    # When practical_verified_at is set -> False
    training_enrollment_a.practical_verified_at = timezone.now()
    assert training_enrollment_a.requires_practical_verification is False

    # When course assessment method does not require practical demo -> False
    training_enrollment_a.practical_verified_at = None
    for method in ["written_exam", "attendance_only", "manager_evaluation"]:
        quality_course_a.assessment_method = method
        quality_course_a.save()
        assert training_enrollment_a.requires_practical_verification is False


@pytest.mark.django_db
def test_trainingcompetency_enrollment_badges(training_enrollment_a):
    """Verify badge properties for TrainingEnrollment (reason, practical rating, status)."""
    # Reason badges
    for reason, expected_badge in TrainingEnrollment.ASSIGNMENT_REASON_CSS.items():
        training_enrollment_a.assignment_reason = reason
        assert training_enrollment_a.reason_badge == expected_badge
    training_enrollment_a.assignment_reason = "unknown_reason"
    assert training_enrollment_a.reason_badge == "badge-slate"

    # Practical rating badges
    for rating, expected_badge in TrainingEnrollment.PRACTICAL_RATING_CSS.items():
        training_enrollment_a.practical_rating = rating
        assert training_enrollment_a.practical_rating_badge == expected_badge
    training_enrollment_a.practical_rating = None
    assert training_enrollment_a.practical_rating_badge == "badge-slate"

    # Status badges
    for status, expected_badge in TrainingEnrollment.STATUS_CSS.items():
        training_enrollment_a.status = status
        training_enrollment_a.due_date = _trainingcompetency_make_date(10)
        assert training_enrollment_a.status_badge == expected_badge

    # Overdue override: status is assigned or in_progress but past due -> badge-red
    training_enrollment_a.status = "assigned"
    training_enrollment_a.due_date = _trainingcompetency_make_date(-5)
    assert training_enrollment_a.status_badge == "badge-red"

    training_enrollment_a.status = "in_progress"
    training_enrollment_a.due_date = _trainingcompetency_make_date(-2)
    assert training_enrollment_a.status_badge == "badge-red"


@pytest.mark.django_db
def test_trainingcompetency_enrollment_protected_fks(training_enrollment_a, quality_course_a, admin_user):
    """Verify PROTECT foreign keys on course and trainee prevent accidental deletion."""
    with pytest.raises(models.ProtectedError):
        quality_course_a.delete()

    with pytest.raises(models.ProtectedError):
        admin_user.delete()


@pytest.mark.django_db
def test_trainingcompetency_enrollment_unique_constraint(training_enrollment_a, tenant_a, quality_course_a, admin_user):
    """Verify composite uniqueness on (tenant, number) for TrainingEnrollment."""
    with pytest.raises(IntegrityError):
        TrainingEnrollment.objects.create(
            tenant=tenant_a,
            number=training_enrollment_a.number,
            course=quality_course_a,
            trainee=admin_user,
            assigned_date=_trainingcompetency_make_date(0),
            due_date=_trainingcompetency_make_date(30),
        )


# ============================================================================
# 4. CompetencyCertification Model Tests (QCERT)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_certification_creation_and_autonumber(competency_certification_a, tenant_a, quality_course_a, admin_user):
    """Verify CompetencyCertification creation, QCERT prefix, defaults, and certificate_hash."""
    assert competency_certification_a.pk is not None
    assert competency_certification_a.number.startswith("QCERT-")
    assert competency_certification_a.tenant == tenant_a
    assert competency_certification_a.trainee == admin_user
    assert competency_certification_a.course == quality_course_a
    assert competency_certification_a.status == "active"
    assert competency_certification_a.qualification_level == "level_2_qualified"
    assert competency_certification_a.renewal_interval_months == 12
    assert len(competency_certification_a.certificate_hash) == 64


@pytest.mark.django_db
def test_trainingcompetency_certification_str(competency_certification_a):
    """Verify CompetencyCertification __str__ format: {number} - {qualification_title} ({trainee.username})."""
    expected = f"{competency_certification_a.number} - {competency_certification_a.qualification_title} ({competency_certification_a.trainee.username})"
    assert str(competency_certification_a) == expected


@pytest.mark.django_db
def test_trainingcompetency_certification_hash_generation(tenant_a, quality_course_a, admin_user):
    """Verify generate_certificate_hash SHA-256 calculation and auto-generation on save."""
    issue_date = timezone.now().date()
    cert = CompetencyCertification(
        tenant=tenant_a,
        trainee=admin_user,
        course=quality_course_a,
        qualification_title="Manual Hash Test Cert",
        issue_date=issue_date,
        certified_by=admin_user,
    )
    expected_seed = f"{tenant_a.pk}:{admin_user.pk}:{quality_course_a.pk}:{issue_date}:{settings.SECRET_KEY}"
    expected_hash = hashlib.sha256(expected_seed.encode()).hexdigest()

    assert cert.generate_certificate_hash() == expected_hash

    # Save should populate cert.certificate_hash automatically if empty
    cert.save()
    assert cert.certificate_hash == expected_hash


@pytest.mark.django_db
def test_trainingcompetency_certification_is_valid(competency_certification_a):
    """Verify is_valid property handles expiration dates and statuses correctly."""
    today = timezone.now().date()

    # Active and valid in future -> True
    competency_certification_a.status = "active"
    competency_certification_a.valid_until = today + timedelta(days=100)
    assert competency_certification_a.is_valid is True

    # Active with no expiration date (permanent certification) -> True
    competency_certification_a.valid_until = None
    assert competency_certification_a.is_valid is True

    # Active but valid_until is yesterday -> False
    competency_certification_a.valid_until = today - timedelta(days=1)
    assert competency_certification_a.is_valid is False

    # Future date but status is suspended, revoked, expired, or superseded -> False
    competency_certification_a.valid_until = today + timedelta(days=100)
    for non_active in ["expiring_soon", "expired", "suspended", "revoked", "superseded"]:
        competency_certification_a.status = non_active
        assert competency_certification_a.is_valid is False


@pytest.mark.django_db
def test_trainingcompetency_certification_days_until_expiration(competency_certification_a):
    """Verify days_until_expiration calculation."""
    today = timezone.now().date()

    competency_certification_a.valid_until = today + timedelta(days=45)
    assert competency_certification_a.days_until_expiration == 45

    competency_certification_a.valid_until = today - timedelta(days=10)
    assert competency_certification_a.days_until_expiration == -10

    competency_certification_a.valid_until = None
    assert competency_certification_a.days_until_expiration is None


@pytest.mark.django_db
def test_trainingcompetency_certification_is_expiring_soon_and_is_expired(competency_certification_a):
    """Verify is_expiring_soon (0 to 30 days) and is_expired (<0 days) properties."""
    today = timezone.now().date()

    # 20 days remaining -> expiring soon = True, expired = False
    competency_certification_a.valid_until = today + timedelta(days=20)
    assert competency_certification_a.is_expiring_soon is True
    assert competency_certification_a.is_expired is False

    # 30 days remaining (inclusive boundary) -> expiring soon = True, expired = False
    competency_certification_a.valid_until = today + timedelta(days=30)
    assert competency_certification_a.is_expiring_soon is True
    assert competency_certification_a.is_expired is False

    # 31 days remaining -> expiring soon = False, expired = False
    competency_certification_a.valid_until = today + timedelta(days=31)
    assert competency_certification_a.is_expiring_soon is False
    assert competency_certification_a.is_expired is False

    # 0 days remaining (expires today) -> expiring soon = True, expired = False
    competency_certification_a.valid_until = today
    assert competency_certification_a.is_expiring_soon is True
    assert competency_certification_a.is_expired is False

    # -1 day (expired yesterday) -> expiring soon = False, expired = True
    competency_certification_a.valid_until = today - timedelta(days=1)
    assert competency_certification_a.is_expiring_soon is False
    assert competency_certification_a.is_expired is True

    # Permanent certification (valid_until = None) -> both False
    competency_certification_a.valid_until = None
    assert competency_certification_a.is_expiring_soon is False
    assert competency_certification_a.is_expired is False


@pytest.mark.django_db
def test_trainingcompetency_certification_badges(competency_certification_a):
    """Verify level_badge and status_badge properties (including expiration overrides)."""
    # Level badges
    for level, expected_badge in CompetencyCertification.QUALIFICATION_LEVEL_CSS.items():
        competency_certification_a.qualification_level = level
        assert competency_certification_a.level_badge == expected_badge
    competency_certification_a.qualification_level = "unknown_level"
    assert competency_certification_a.level_badge == "badge-slate"

    # Status badges
    for status, expected_badge in CompetencyCertification.STATUS_CSS.items():
        competency_certification_a.status = status
        competency_certification_a.valid_until = _trainingcompetency_make_date(60)
        assert competency_certification_a.status_badge == expected_badge

    # Overrides for active status:
    competency_certification_a.status = "active"

    # 1. Expired -> badge-red
    competency_certification_a.valid_until = _trainingcompetency_make_date(-5)
    assert competency_certification_a.status_badge == "badge-red"

    # 2. Expiring soon (<30 days) -> badge-amber
    competency_certification_a.valid_until = _trainingcompetency_make_date(15)
    assert competency_certification_a.status_badge == "badge-amber"

    # 3. Valid far in future -> badge-green
    competency_certification_a.valid_until = _trainingcompetency_make_date(180)
    assert competency_certification_a.status_badge == "badge-green"


@pytest.mark.django_db
def test_trainingcompetency_certification_protected_fks(competency_certification_a, quality_course_a, admin_user):
    """Verify PROTECT on trainee, course, and certified_by foreign keys."""
    with pytest.raises(models.ProtectedError):
        quality_course_a.delete()

    with pytest.raises(models.ProtectedError):
        admin_user.delete()


@pytest.mark.django_db
def test_trainingcompetency_certification_unique_constraint(competency_certification_a, tenant_a, quality_course_a, admin_user):
    """Verify composite uniqueness on (tenant, number) for CompetencyCertification."""
    with pytest.raises(IntegrityError):
        CompetencyCertification.objects.create(
            tenant=tenant_a,
            number=competency_certification_a.number,
            trainee=admin_user,
            course=quality_course_a,
            qualification_title="Duplicate Cert Number",
            issue_date=_trainingcompetency_make_date(0),
            certified_by=admin_user,
        )


# ============================================================================
# 5. Multi-Tenant Isolation Tests
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_tenant_isolation(
    tenant_a, tenant_b,
    competency_matrix_a, competency_matrix_b,
    quality_course_a, quality_course_b,
    training_enrollment_a, training_enrollment_b,
    competency_certification_a, competency_certification_b,
):
    """Verify tenant isolation across all four Training & Competency Management models."""
    # CompetencyMatrix
    assert competency_matrix_a.tenant == tenant_a
    assert competency_matrix_b.tenant == tenant_b
    assert not CompetencyMatrix.objects.filter(tenant=tenant_a, id=competency_matrix_b.id).exists()
    assert not CompetencyMatrix.objects.filter(tenant=tenant_b, id=competency_matrix_a.id).exists()

    # QualityTrainingCourse
    assert quality_course_a.tenant == tenant_a
    assert quality_course_b.tenant == tenant_b
    assert not QualityTrainingCourse.objects.filter(tenant=tenant_a, id=quality_course_b.id).exists()
    assert not QualityTrainingCourse.objects.filter(tenant=tenant_b, id=quality_course_a.id).exists()

    # TrainingEnrollment
    assert training_enrollment_a.tenant == tenant_a
    assert training_enrollment_b.tenant == tenant_b
    assert not TrainingEnrollment.objects.filter(tenant=tenant_a, id=training_enrollment_b.id).exists()
    assert not TrainingEnrollment.objects.filter(tenant=tenant_b, id=training_enrollment_a.id).exists()

    # CompetencyCertification
    assert competency_certification_a.tenant == tenant_a
    assert competency_certification_b.tenant == tenant_b
    assert not CompetencyCertification.objects.filter(tenant=tenant_a, id=competency_certification_b.id).exists()
    assert not CompetencyCertification.objects.filter(tenant=tenant_b, id=competency_certification_a.id).exists()
