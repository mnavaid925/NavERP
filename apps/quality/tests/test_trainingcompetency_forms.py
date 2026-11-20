"""Unit tests for Quality Management Sub-module 12.12: Training & Competency Management forms.

Tests forms:
1. CompetencyMatrixForm
2. QualityTrainingCourseForm
3. TrainingEnrollmentForm
4. TrainingCompletionForm
5. PracticalVerificationForm
6. TrainingWaiverForm
7. CompetencyCertificationForm
8. CertificationSuspensionForm
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.quality.forms._common import reject_foreign
from apps.quality.forms.TrainingCompetency import (
    CertificationSuspensionForm,
    CompetencyCertificationForm,
    CompetencyMatrixForm,
    PracticalVerificationForm,
    QualityTrainingCourseForm,
    TrainingCompletionForm,
    TrainingEnrollmentForm,
    TrainingWaiverForm,
)
from apps.quality.models import (
    CompetencyCertification,
    CompetencyMatrix,
    QualityTrainingCourse,
    TrainingEnrollment,
)

User = get_user_model()


def _trainingcompetency_matrix_payload(department_pk=None, **overrides):
    """Generate default valid payload for CompetencyMatrixForm."""
    data = {
        "title": "Aseptic Fill Line Operator Competency Matrix",
        "role_title": "Cleanroom Technician",
        "qualification_tier": "independent",
        "criticality": "critical_gxp",
        "revision": "1.0",
        "minimum_passing_score": 80,
        "validity_period_months": 12,
        "prerequisite_experience_months": 6,
        "description": "Comprehensive core competency curriculum for aseptic cleanrooms.",
        "notes": "Reviewed annually in Q4.",
    }
    if department_pk is not None:
        data["department"] = department_pk
    data.update(overrides)
    return data


def _trainingcompetency_course_payload(matrix_pk, doc_pk=None, user_pk=None, provider_pk=None, **overrides):
    """Generate default valid payload for QualityTrainingCourseForm."""
    data = {
        "title": "SOP-0042 Aseptic Gowning and Cleanroom Entry Protocol",
        "competency_matrix": matrix_pk,
        "course_code": "TRN-SOP-0042",
        "category": "gxp_compliance",
        "delivery_method": "blended",
        "assessment_method": "both_exam_and_ojt",
        "document_revision": "1.0",
        "retrain_on_revision": True,
        "duration_hours": "2.50",
        "passing_score": 80,
        "ojt_checklist_criteria": "1. Correct gowning sequence.\n2. Particle count sign-off.",
        "syllabus_summary": "Cleanroom entry, gowning, and gowning validation procedures.",
        "notes": "Annual mandatory course for all sterile core operators.",
    }
    if doc_pk is not None:
        data["controlled_document"] = doc_pk
    if user_pk is not None:
        data["instructor"] = user_pk
    if provider_pk is not None:
        data["external_provider"] = provider_pk
    data.update(overrides)
    return data


def _trainingcompetency_enrollment_payload(course_pk, trainee_pk, **overrides):
    """Generate default valid payload for TrainingEnrollmentForm."""
    today = timezone.now().date()
    data = {
        "course": course_pk,
        "trainee": trainee_pk,
        "assignment_reason": "annual_refresher",
        "assigned_date": today,
        "due_date": today + timedelta(days=30),
        "notes": "Standard annual re-qualification assignment.",
    }
    data.update(overrides)
    return data


def _trainingcompetency_certification_payload(enrollment_pk, trainee_pk, course_pk, matrix_pk, **overrides):
    """Generate default valid payload for CompetencyCertificationForm."""
    today = timezone.now().date()
    data = {
        "enrollment": enrollment_pk,
        "trainee": trainee_pk,
        "course": course_pk,
        "competency_matrix": matrix_pk,
        "qualification_title": "Certified Aseptic Cleanroom Operator",
        "qualification_level": "level_2_qualified",
        "issue_date": today,
        "valid_until": today + timedelta(days=365),
        "renewal_interval_months": 12,
        "authorized_work_centers": "Cleanroom Suite Alpha, Fill Line 1",
        "notes": "Passed written exam and practical gowning qualification.",
    }
    data.update(overrides)
    return data


# ============================================================================
# 1. CompetencyMatrixForm Tests
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_form_excluded_fields():
    """Verify system, workflow, and lifecycle fields are strictly excluded from CompetencyMatrixForm."""
    excluded = {
        "tenant",
        "number",
        "status",
        "approved_by",
        "approval_date",
        "created_at",
        "updated_at",
    }
    for field_name in excluded:
        assert field_name not in CompetencyMatrixForm.Meta.fields


@pytest.mark.django_db
def test_trainingcompetency_matrix_form_valid_submission(tenant_a, quality_department):
    """Verify CompetencyMatrixForm validates and saves with valid data and department FK."""
    payload = _trainingcompetency_matrix_payload(department_pk=quality_department.pk)
    form = CompetencyMatrixForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()

    assert obj.pk is not None
    assert obj.number.startswith("QMTX-")
    assert obj.title == "Aseptic Fill Line Operator Competency Matrix"
    assert obj.department == quality_department
    assert obj.minimum_passing_score == 80
    assert obj.validity_period_months == 12
    assert obj.status == "draft"  # Default status preserved


@pytest.mark.django_db
def test_trainingcompetency_matrix_form_invalid_missing_required(tenant_a):
    """Verify CompetencyMatrixForm fails when required fields are missing."""
    # title and role_title are required
    form = CompetencyMatrixForm(data={"minimum_passing_score": 80}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "role_title" in form.errors


@pytest.mark.django_db
def test_trainingcompetency_matrix_form_fk_scoping(tenant_a, tenant_b, quality_department, quality_department_b):
    """Verify department queryset in CompetencyMatrixForm is strictly filtered by tenant."""
    form_a = CompetencyMatrixForm(tenant=tenant_a)
    dept_qs_a = form_a.fields["department"].queryset
    assert quality_department in dept_qs_a
    assert quality_department_b not in dept_qs_a

    form_b = CompetencyMatrixForm(tenant=tenant_b)
    dept_qs_b = form_b.fields["department"].queryset
    assert quality_department_b in dept_qs_b
    assert quality_department not in dept_qs_b

    # Unbound / no tenant provided initializes cleanly
    form_no_tenant = CompetencyMatrixForm()
    assert form_no_tenant.fields["department"].queryset is not None


@pytest.mark.django_db
def test_trainingcompetency_matrix_form_reject_foreign_direct(tenant_a, quality_department_b):
    """Directly verify reject_foreign detects cross-tenant department on CompetencyMatrixForm."""
    form = CompetencyMatrixForm(tenant=tenant_a)
    form.cleaned_data = {"department": quality_department_b}
    reject_foreign(form, form.cleaned_data, ["department"])
    assert "department" in form.errors
    assert "That record belongs to another workspace." in str(form.errors["department"])


@pytest.mark.django_db
def test_trainingcompetency_matrix_form_reject_foreign_bound(tenant_a, quality_department_b):
    """Verify bound CompetencyMatrixForm rejects submission of a cross-tenant department PK."""
    payload = _trainingcompetency_matrix_payload(department_pk=quality_department_b.pk)
    form = CompetencyMatrixForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "department" in form.errors


@pytest.mark.django_db
def test_trainingcompetency_matrix_form_update_instance(tenant_a, competency_matrix_a, quality_department):
    """Verify CompetencyMatrixForm properly binds and updates an existing instance."""
    payload = _trainingcompetency_matrix_payload(
        department_pk=quality_department.pk,
        title="Updated Aseptic Matrix Title",
        revision="2.0",
        minimum_passing_score=85,
    )
    form = CompetencyMatrixForm(instance=competency_matrix_a, data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == competency_matrix_a.pk
    assert updated.title == "Updated Aseptic Matrix Title"
    assert updated.revision == "2.0"
    assert updated.minimum_passing_score == 85


# ============================================================================
# 2. QualityTrainingCourseForm Tests
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_course_form_excluded_fields():
    """Verify system, workflow, and lifecycle fields are excluded from QualityTrainingCourseForm."""
    excluded = {
        "tenant",
        "number",
        "status",
        "created_at",
        "updated_at",
    }
    for field_name in excluded:
        assert field_name not in QualityTrainingCourseForm.Meta.fields


@pytest.mark.django_db
def test_trainingcompetency_course_form_valid_submission(
    tenant_a,
    competency_matrix_a,
    quality_doc_effective,
    admin_user,
    supplier_party_a,
):
    """Verify QualityTrainingCourseForm validates and saves with all tenant-scoped foreign keys."""
    payload = _trainingcompetency_course_payload(
        matrix_pk=competency_matrix_a.pk,
        doc_pk=quality_doc_effective.pk,
        user_pk=admin_user.pk,
        provider_pk=supplier_party_a.pk,
    )
    form = QualityTrainingCourseForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()

    assert obj.pk is not None
    assert obj.number.startswith("QCRS-")
    assert obj.title == "SOP-0042 Aseptic Gowning and Cleanroom Entry Protocol"
    assert obj.competency_matrix == competency_matrix_a
    assert obj.controlled_document == quality_doc_effective
    assert obj.instructor == admin_user
    assert obj.external_provider == supplier_party_a
    assert obj.duration_hours == Decimal("2.50")
    assert obj.passing_score == 80
    assert obj.retrain_on_revision is True
    assert obj.status == "draft"  # Default status preserved


@pytest.mark.django_db
def test_trainingcompetency_course_form_invalid_missing_title(tenant_a, competency_matrix_a):
    """Verify QualityTrainingCourseForm fails validation when course title is missing."""
    payload = _trainingcompetency_course_payload(matrix_pk=competency_matrix_a.pk, title="")
    form = QualityTrainingCourseForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


@pytest.mark.django_db
def test_trainingcompetency_course_form_fk_scoping(
    tenant_a,
    tenant_b,
    competency_matrix_a,
    competency_matrix_b,
    quality_doc_effective,
    quality_doc_b,
    supplier_party_a,
    supplier_party_b,
    admin_user,
    admin_b,
):
    """Verify all 4 foreign key querysets are scoped to the given tenant."""
    # Create an inactive user in tenant_a to verify active filter
    inactive_user = User.objects.create_user(
        username="inactive_trainer",
        email="inactive_trainer@acme.com",
        password="Pass123!",
        tenant=tenant_a,
        is_active=False,
    )

    form_a = QualityTrainingCourseForm(tenant=tenant_a)

    # 1. competency_matrix
    matrix_qs_a = form_a.fields["competency_matrix"].queryset
    assert competency_matrix_a in matrix_qs_a
    assert competency_matrix_b not in matrix_qs_a

    # 2. controlled_document
    doc_qs_a = form_a.fields["controlled_document"].queryset
    assert quality_doc_effective in doc_qs_a
    assert quality_doc_b not in doc_qs_a

    # 3. external_provider
    provider_qs_a = form_a.fields["external_provider"].queryset
    assert supplier_party_a in provider_qs_a
    assert supplier_party_b not in provider_qs_a

    # 4. instructor
    instructor_qs_a = form_a.fields["instructor"].queryset
    assert admin_user in instructor_qs_a
    assert admin_b not in instructor_qs_a
    assert inactive_user not in instructor_qs_a  # must be active


@pytest.mark.django_db
def test_trainingcompetency_course_form_reject_foreign_direct(
    tenant_a,
    competency_matrix_b,
    quality_doc_b,
    supplier_party_b,
    admin_b,
):
    """Directly test reject_foreign rejects foreign tenant FKs on QualityTrainingCourseForm."""
    form = QualityTrainingCourseForm(tenant=tenant_a)
    form.cleaned_data = {
        "competency_matrix": competency_matrix_b,
        "controlled_document": quality_doc_b,
        "external_provider": supplier_party_b,
        "instructor": admin_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["competency_matrix", "controlled_document", "external_provider", "instructor"],
    )
    for field_name in ["competency_matrix", "controlled_document", "external_provider", "instructor"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


@pytest.mark.django_db
def test_trainingcompetency_course_form_reject_foreign_bound(
    tenant_a,
    competency_matrix_b,
    quality_doc_b,
    supplier_party_b,
    admin_b,
):
    """Verify bound QualityTrainingCourseForm rejects foreign tenant PK inputs."""
    payload = _trainingcompetency_course_payload(
        matrix_pk=competency_matrix_b.pk,
        doc_pk=quality_doc_b.pk,
        user_pk=admin_b.pk,
        provider_pk=supplier_party_b.pk,
    )
    form = QualityTrainingCourseForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "competency_matrix" in form.errors
    assert "controlled_document" in form.errors
    assert "instructor" in form.errors
    assert "external_provider" in form.errors


@pytest.mark.django_db
def test_trainingcompetency_course_form_update_instance(
    tenant_a,
    quality_course_a,
    competency_matrix_a,
):
    """Verify QualityTrainingCourseForm updates an existing course instance."""
    payload = _trainingcompetency_course_payload(
        matrix_pk=competency_matrix_a.pk,
        title="Updated Course Title",
        duration_hours="3.75",
        passing_score=85,
    )
    form = QualityTrainingCourseForm(instance=quality_course_a, data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == quality_course_a.pk
    assert updated.title == "Updated Course Title"
    assert updated.duration_hours == Decimal("3.75")
    assert updated.passing_score == 85


# ============================================================================
# 3. TrainingEnrollmentForm Tests
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_excluded_fields():
    """Verify execution, evaluation, verification, and audit fields are strictly excluded from TrainingEnrollmentForm."""
    excluded = {
        "tenant",
        "number",
        "status",
        "completion_date",
        "score",
        "is_passed",
        "self_certified",
        "self_certified_at",
        "practical_evaluation_notes",
        "practical_verified_by",
        "practical_verified_at",
        "practical_rating",
        "waiver_reason",
        "waived_by",
        "waived_at",
        "created_at",
        "updated_at",
    }
    for field_name in excluded:
        assert field_name not in TrainingEnrollmentForm.Meta.fields


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_valid_submission(
    tenant_a,
    quality_course_a,
    admin_user,
    quality_dco,
    capa_action_a,
):
    """Verify TrainingEnrollmentForm validates and saves with valid course, trainee, DCO, and CAPA."""
    today = timezone.now().date()
    payload = _trainingcompetency_enrollment_payload(
        course_pk=quality_course_a.pk,
        trainee_pk=admin_user.pk,
        document_change_order=quality_dco.pk,
        capa_action=capa_action_a.pk,
        assigned_date=today,
        due_date=today + timedelta(days=21),
    )
    form = TrainingEnrollmentForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()

    assert obj.pk is not None
    assert obj.number.startswith("QENR-")
    assert obj.course == quality_course_a
    assert obj.trainee == admin_user
    assert obj.document_change_order == quality_dco
    assert obj.capa_action == capa_action_a
    assert obj.status == "assigned"


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_due_date_before_assigned_date(
    tenant_a,
    quality_course_a,
    admin_user,
):
    """Verify clean() rejects due_date earlier than assigned_date."""
    today = timezone.now().date()
    payload = _trainingcompetency_enrollment_payload(
        course_pk=quality_course_a.pk,
        trainee_pk=admin_user.pk,
        assigned_date=today,
        due_date=today - timedelta(days=1),
    )
    form = TrainingEnrollmentForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "due_date" in form.errors
    assert "Due date cannot be earlier than assigned date." in str(form.errors["due_date"])


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_same_day_dates_valid(
    tenant_a,
    quality_course_a,
    admin_user,
):
    """Verify due_date equal to assigned_date is valid (e.g. same-day urgent training)."""
    today = timezone.now().date()
    payload = _trainingcompetency_enrollment_payload(
        course_pk=quality_course_a.pk,
        trainee_pk=admin_user.pk,
        assigned_date=today,
        due_date=today,
    )
    form = TrainingEnrollmentForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_missing_required_fields(tenant_a):
    """Verify TrainingEnrollmentForm requires course, trainee, and assignment_reason."""
    form = TrainingEnrollmentForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "course" in form.errors
    assert "trainee" in form.errors


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_fk_scoping(
    tenant_a,
    tenant_b,
    quality_course_a,
    quality_course_b,
    admin_user,
    admin_b,
    quality_dco,
    quality_dco_b,
    capa_action_a,
    capa_action_b,
):
    """Verify FK querysets are filtered by tenant and active status."""
    # Create a draft course in tenant_a to verify status="active" filtering on courses
    draft_course = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        title="Draft Unpublished Course",
        category="general",
        status="draft",
        passing_score=75,
    )

    form_a = TrainingEnrollmentForm(tenant=tenant_a)

    # 1. course must be tenant_a AND active
    course_qs_a = form_a.fields["course"].queryset
    assert quality_course_a in course_qs_a
    assert quality_course_b not in course_qs_a
    assert draft_course not in course_qs_a

    # 2. trainee must be tenant_a and active
    trainee_qs_a = form_a.fields["trainee"].queryset
    assert admin_user in trainee_qs_a
    assert admin_b not in trainee_qs_a

    # 3. document_change_order
    dco_qs_a = form_a.fields["document_change_order"].queryset
    assert quality_dco in dco_qs_a
    assert quality_dco_b not in dco_qs_a

    # 4. capa_action
    capa_qs_a = form_a.fields["capa_action"].queryset
    assert capa_action_a in capa_qs_a
    assert capa_action_b not in capa_qs_a


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_reject_foreign_direct(
    tenant_a,
    quality_course_b,
    admin_b,
    quality_dco_b,
    capa_action_b,
):
    """Directly test reject_foreign on TrainingEnrollmentForm foreign keys."""
    form = TrainingEnrollmentForm(tenant=tenant_a)
    form.cleaned_data = {
        "course": quality_course_b,
        "trainee": admin_b,
        "document_change_order": quality_dco_b,
        "capa_action": capa_action_b,
    }
    reject_foreign(form, form.cleaned_data, ["course", "trainee", "document_change_order", "capa_action"])
    for field_name in ["course", "trainee", "document_change_order", "capa_action"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


@pytest.mark.django_db
def test_trainingcompetency_enrollment_form_reject_foreign_bound(
    tenant_a,
    quality_course_b,
    admin_b,
):
    """Verify bound TrainingEnrollmentForm rejects foreign course and trainee PKs."""
    payload = _trainingcompetency_enrollment_payload(
        course_pk=quality_course_b.pk,
        trainee_pk=admin_b.pk,
    )
    form = TrainingEnrollmentForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "course" in form.errors
    assert "trainee" in form.errors


# ============================================================================
# 4. TrainingCompletionForm Tests
# ============================================================================

def test_trainingcompetency_completion_form_valid_score():
    """Verify TrainingCompletionForm validates various valid scores."""
    valid_scores = ["0.00", "50", "85.50", "100.00", 95]
    for sc in valid_scores:
        form = TrainingCompletionForm(data={"score": sc, "notes": "Completed assessment."})
        assert form.is_valid(), f"Score {sc} should be valid: {form.errors}"
        assert form.cleaned_data["score"] == Decimal(str(sc))


def test_trainingcompetency_completion_form_optional_score():
    """Verify TrainingCompletionForm permits empty score for non-numeric courses."""
    form = TrainingCompletionForm(data={"notes": "Read and understood SOP."})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["score"] is None


def test_trainingcompetency_completion_form_negative_score_rejected():
    """Verify TrainingCompletionForm rejects negative scores."""
    form = TrainingCompletionForm(data={"score": "-5.00"})
    assert not form.is_valid()
    assert "score" in form.errors


def test_trainingcompetency_completion_form_over_100_score_rejected():
    """Verify TrainingCompletionForm rejects scores exceeding 100%."""
    form = TrainingCompletionForm(data={"score": "105.00"})
    assert not form.is_valid()
    assert "score" in form.errors


# ============================================================================
# 5. PracticalVerificationForm Tests
# ============================================================================

def test_trainingcompetency_practical_verification_form_fields():
    """Verify PracticalVerificationForm contains exactly practical_rating and practical_evaluation_notes."""
    form = PracticalVerificationForm()
    assert set(form.fields.keys()) == {"practical_rating", "practical_evaluation_notes"}


def test_trainingcompetency_practical_verification_form_valid():
    """Verify PracticalVerificationForm validates with proper rating and observation notes."""
    payload = {
        "practical_rating": "meets_standard",
        "practical_evaluation_notes": "Candidate demonstrated proper sterile gowning sequence and glove sanitization.",
    }
    form = PracticalVerificationForm(data=payload)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["practical_rating"] == "meets_standard"
    assert "sterile gowning" in form.cleaned_data["practical_evaluation_notes"]


def test_trainingcompetency_practical_verification_form_all_choices():
    """Verify each allowed practical proficiency choice is valid."""
    choices = ["exceeds_standard", "meets_standard", "needs_improvement", "unsatisfactory"]
    for ch in choices:
        form = PracticalVerificationForm(data={
            "practical_rating": ch,
            "practical_evaluation_notes": f"Evaluation notes for {ch}.",
        })
        assert form.is_valid(), f"Rating {ch} failed: {form.errors}"


def test_trainingcompetency_practical_verification_form_invalid_choice():
    """Verify PracticalVerificationForm rejects unknown rating choices."""
    form = PracticalVerificationForm(data={
        "practical_rating": "not_a_valid_choice",
        "practical_evaluation_notes": "Some notes.",
    })
    assert not form.is_valid()
    assert "practical_rating" in form.errors


def test_trainingcompetency_practical_verification_form_missing_notes():
    """Verify practical_evaluation_notes is required."""
    form = PracticalVerificationForm(data={"practical_rating": "meets_standard", "practical_evaluation_notes": ""})
    assert not form.is_valid()
    assert "practical_evaluation_notes" in form.errors


# ============================================================================
# 6. TrainingWaiverForm Tests
# ============================================================================

def test_trainingcompetency_waiver_form_valid():
    """Verify TrainingWaiverForm validates with non-empty waiver justification."""
    form = TrainingWaiverForm(data={
        "waiver_reason": "Employee has 10+ years equivalent aseptic cleanroom experience verified by prior certification."
    })
    assert form.is_valid(), form.errors
    assert "10+ years" in form.cleaned_data["waiver_reason"]


def test_trainingcompetency_waiver_form_missing_reason():
    """Verify TrainingWaiverForm requires waiver_reason."""
    form = TrainingWaiverForm(data={"waiver_reason": ""})
    assert not form.is_valid()
    assert "waiver_reason" in form.errors


# ============================================================================
# 7. CompetencyCertificationForm Tests
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_certification_form_excluded_fields():
    """Verify system, hash, signature, and approval fields are strictly excluded from CompetencyCertificationForm."""
    excluded = {
        "tenant",
        "number",
        "status",
        "certificate_hash",
        "electronic_signature",
        "suspension_reason",
        "certified_by",
        "created_at",
        "updated_at",
    }
    for field_name in excluded:
        assert field_name not in CompetencyCertificationForm.Meta.fields


@pytest.mark.django_db
def test_trainingcompetency_certification_form_valid_submission(
    tenant_a,
    training_enrollment_a,
    admin_user,
    quality_course_a,
    competency_matrix_a,
):
    """Verify CompetencyCertificationForm validates and saves with consistent enrollment relations."""
    payload = _trainingcompetency_certification_payload(
        enrollment_pk=training_enrollment_a.pk,
        trainee_pk=admin_user.pk,
        course_pk=quality_course_a.pk,
        matrix_pk=competency_matrix_a.pk,
    )
    form = CompetencyCertificationForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.certified_by = admin_user
    obj.certificate_hash = obj.generate_certificate_hash()
    obj.save()

    assert obj.pk is not None
    assert obj.number.startswith("QCERT-")
    assert obj.enrollment == training_enrollment_a
    assert obj.trainee == admin_user
    assert obj.course == quality_course_a
    assert obj.competency_matrix == competency_matrix_a
    assert obj.status == "active"
    assert len(obj.certificate_hash) == 64


@pytest.mark.django_db
def test_trainingcompetency_certification_form_expiration_before_issue_date(
    tenant_a,
    training_enrollment_a,
    admin_user,
    quality_course_a,
    competency_matrix_a,
):
    """Verify clean() rejects valid_until earlier than issue_date."""
    today = timezone.now().date()
    payload = _trainingcompetency_certification_payload(
        enrollment_pk=training_enrollment_a.pk,
        trainee_pk=admin_user.pk,
        course_pk=quality_course_a.pk,
        matrix_pk=competency_matrix_a.pk,
        issue_date=today,
        valid_until=today - timedelta(days=1),
    )
    form = CompetencyCertificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "valid_until" in form.errors
    assert "Expiration date cannot be earlier than issue date." in str(form.errors["valid_until"])


@pytest.mark.django_db
def test_trainingcompetency_certification_form_trainee_mismatch_with_enrollment(
    tenant_a,
    training_enrollment_a,
    member_user,
    quality_course_a,
    competency_matrix_a,
):
    """Verify clean() detects when submitted trainee differs from enrollment trainee."""
    # training_enrollment_a is for admin_user; submit member_user instead
    payload = _trainingcompetency_certification_payload(
        enrollment_pk=training_enrollment_a.pk,
        trainee_pk=member_user.pk,
        course_pk=quality_course_a.pk,
        matrix_pk=competency_matrix_a.pk,
    )
    form = CompetencyCertificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "trainee" in form.errors
    assert "Trainee does not match the bound training enrollment." in str(form.errors["trainee"])


@pytest.mark.django_db
def test_trainingcompetency_certification_form_course_mismatch_with_enrollment(
    tenant_a,
    training_enrollment_a,
    admin_user,
    competency_matrix_a,
):
    """Verify clean() detects when submitted course differs from enrollment course."""
    other_course = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="Alternative Course In Same Matrix",
        category="general",
        status="active",
        passing_score=80,
    )
    # training_enrollment_a is for quality_course_a; submit other_course instead
    payload = _trainingcompetency_certification_payload(
        enrollment_pk=training_enrollment_a.pk,
        trainee_pk=admin_user.pk,
        course_pk=other_course.pk,
        matrix_pk=competency_matrix_a.pk,
    )
    form = CompetencyCertificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "course" in form.errors
    assert "Course does not match the bound training enrollment." in str(form.errors["course"])


@pytest.mark.django_db
def test_trainingcompetency_certification_form_matrix_mismatch_with_course(
    tenant_a,
    training_enrollment_a,
    admin_user,
    quality_course_a,
    quality_department,
):
    """Verify clean() detects when submitted competency matrix differs from course.competency_matrix."""
    other_matrix = CompetencyMatrix.objects.create(
        tenant=tenant_a,
        title="Different Unrelated Matrix",
        role_title="Packaging Operator",
        department=quality_department,
        status="active",
        minimum_passing_score=80,
    )
    # quality_course_a is bound to competency_matrix_a; submit other_matrix instead
    payload = _trainingcompetency_certification_payload(
        enrollment_pk=training_enrollment_a.pk,
        trainee_pk=admin_user.pk,
        course_pk=quality_course_a.pk,
        matrix_pk=other_matrix.pk,
    )
    form = CompetencyCertificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "competency_matrix" in form.errors
    assert "Competency matrix does not match the bound course curriculum." in str(form.errors["competency_matrix"])


@pytest.mark.django_db
def test_trainingcompetency_certification_form_fk_scoping(
    tenant_a,
    tenant_b,
    training_enrollment_a,
    training_enrollment_b,
    admin_user,
    admin_b,
    quality_course_a,
    quality_course_b,
    competency_matrix_a,
    competency_matrix_b,
):
    """Verify enrollment, trainee, course, and competency_matrix querysets are scoped to tenant."""
    form_a = CompetencyCertificationForm(tenant=tenant_a)

    # enrollment
    enr_qs = form_a.fields["enrollment"].queryset
    assert training_enrollment_a in enr_qs
    assert training_enrollment_b not in enr_qs

    # trainee
    trainee_qs = form_a.fields["trainee"].queryset
    assert admin_user in trainee_qs
    assert admin_b not in trainee_qs

    # course
    course_qs = form_a.fields["course"].queryset
    assert quality_course_a in course_qs
    assert quality_course_b not in course_qs

    # competency_matrix
    matrix_qs = form_a.fields["competency_matrix"].queryset
    assert competency_matrix_a in matrix_qs
    assert competency_matrix_b not in matrix_qs


@pytest.mark.django_db
def test_trainingcompetency_certification_form_reject_foreign_direct(
    tenant_a,
    training_enrollment_b,
    admin_b,
    quality_course_b,
    competency_matrix_b,
):
    """Directly test reject_foreign on CompetencyCertificationForm foreign keys."""
    form = CompetencyCertificationForm(tenant=tenant_a)
    form.cleaned_data = {
        "enrollment": training_enrollment_b,
        "trainee": admin_b,
        "course": quality_course_b,
        "competency_matrix": competency_matrix_b,
    }
    reject_foreign(form, form.cleaned_data, ["enrollment", "trainee", "course", "competency_matrix"])
    for field_name in ["enrollment", "trainee", "course", "competency_matrix"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


@pytest.mark.django_db
def test_trainingcompetency_certification_form_reject_foreign_bound(
    tenant_a,
    training_enrollment_b,
    admin_b,
    quality_course_b,
    competency_matrix_b,
):
    """Verify bound CompetencyCertificationForm rejects cross-tenant foreign keys."""
    payload = _trainingcompetency_certification_payload(
        enrollment_pk=training_enrollment_b.pk,
        trainee_pk=admin_b.pk,
        course_pk=quality_course_b.pk,
        matrix_pk=competency_matrix_b.pk,
    )
    form = CompetencyCertificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "enrollment" in form.errors
    assert "trainee" in form.errors
    assert "course" in form.errors
    assert "competency_matrix" in form.errors


# ============================================================================
# 8. CertificationSuspensionForm Tests
# ============================================================================

def test_trainingcompetency_suspension_form_valid():
    """Verify CertificationSuspensionForm validates with non-empty documented rationale."""
    form = CertificationSuspensionForm(data={
        "suspension_reason": "Operator observed violating gowning sterility protocol during media fill batch run #402."
    })
    assert form.is_valid(), form.errors
    assert "gowning sterility" in form.cleaned_data["suspension_reason"]


def test_trainingcompetency_suspension_form_missing_reason():
    """Verify CertificationSuspensionForm requires suspension_reason."""
    form = CertificationSuspensionForm(data={"suspension_reason": ""})
    assert not form.is_valid()
    assert "suspension_reason" in form.errors
