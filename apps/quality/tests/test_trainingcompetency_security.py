"""Security, multi-tenant isolation (IDOR), segregation of duties, and authorization tests
for Quality Management Sub-module 12.12: Training & Competency Management.

Covers:
1. Multi-Tenant IDOR Isolation:
   - Tenant A accessing Tenant B matrix, course, enrollment, certification (detail, edit, delete, actions) returns strict 404
   - Employee Training Dossier cross-tenant parameter filtering (?trainee=tenant_b_user -> safe fallback to self)
   - Cross-tenant foreign key injection on creates (department, matrix, document, course, trainee) is rejected
2. AuthN & AuthZ:
   - Anonymous access to all 35 endpoints redirects to login
   - Deletion views require tenant admin (@tenant_admin_required) -> member_client is rejected with 403 Forbidden
   - Matrix approval & course activation role gating (member_client is blocked)
   - Matrix retire & course retire role gating (member_client is blocked)
   - Enrollment waiver role gating (member_client is blocked)
   - Certification renewal and suspension role gating (member_client is blocked)
3. Segregation of Duties (SoD):
   - Trainee cannot verify their own practical qualification (evaluator independence enforcement)
   - Independent supervisor verification succeeds and auto-issues competency certification
4. Mass Assignment & Field Immutability:
   - Form POST with manipulated 'status', 'number', 'certificate_hash' cannot bypass workflow or alter system numbers
5. Regulatory Integrity & Exam Score Gating:
   - Exam score below passing_score cannot be coerced into 'verified' status via crafted parameters
   - Exam passing on non-practical course auto-issues certification
   - Exam passing on practical-required course halts at 'completed' pending hands-on evaluation
6. CSV Formula Neutralization:
   - Export CSV endpoints neutralize formula injection characters (=, +, -, @)
7. State Machine Lifecycle Bypasses:
   - Cannot approve already approved/retired matrix
   - Cannot retire non-approved matrix
   - Cannot activate already active/retired course
   - Cannot retire non-active course
   - Cannot verify non-completed enrollment
   - Cannot waive verified or waived enrollment
   - Cannot renew suspended or revoked certification
   - Cannot suspend non-active certification
8. HTTP Method Gating:
   - All 13 mutation/action endpoints reject GET requests with 405 Method Not Allowed
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models.OrgUnit import OrgUnit
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.TrainingCompetency.CompetencyCertifications import CompetencyCertification
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment


# ============================================================================
# 1. MULTI-TENANT IDOR ISOLATION (Cross-Tenant Access Returns 404)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_idor_competency_matrix(client_a, competency_matrix_b):
    """Verify Tenant A user accessing Tenant B CompetencyMatrix returns strict 404."""
    pk = competency_matrix_b.pk
    assert client_a.get(reverse("quality:competency_matrix_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:competency_matrix_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_edit", kwargs={"pk": pk}), {"title": "IDOR Hack"}).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_delete", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_approve", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_retire", kwargs={"pk": pk})).status_code == 404


@pytest.mark.django_db
def test_trainingcompetency_idor_training_course(client_a, quality_course_b):
    """Verify Tenant A user accessing Tenant B QualityTrainingCourse returns strict 404."""
    pk = quality_course_b.pk
    assert client_a.get(reverse("quality:training_course_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:training_course_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:training_course_edit", kwargs={"pk": pk}), {"title": "IDOR Hack"}).status_code == 404
    assert client_a.post(reverse("quality:training_course_delete", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:training_course_activate", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:training_course_retire", kwargs={"pk": pk})).status_code == 404


@pytest.mark.django_db
def test_trainingcompetency_idor_training_enrollment(client_a, training_enrollment_b):
    """Verify Tenant A user accessing Tenant B TrainingEnrollment returns strict 404."""
    pk = training_enrollment_b.pk
    assert client_a.get(reverse("quality:training_enrollment_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:training_enrollment_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_edit", kwargs={"pk": pk}), {"notes": "IDOR Hack"}).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_delete", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_complete", kwargs={"pk": pk}), {"score": 95}).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_verify", kwargs={"pk": pk}), {"practical_rating": "meets_standard"}).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_waive", kwargs={"pk": pk}), {"waiver_reason": "IDOR Waiver"}).status_code == 404


@pytest.mark.django_db
def test_trainingcompetency_idor_competency_certification(client_a, competency_certification_b):
    """Verify Tenant A user accessing Tenant B CompetencyCertification returns strict 404."""
    pk = competency_certification_b.pk
    assert client_a.get(reverse("quality:competency_certification_detail", kwargs={"pk": pk})).status_code == 404
    assert client_a.get(reverse("quality:competency_certification_edit", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_edit", kwargs={"pk": pk}), {"qualification_title": "IDOR Hack"}).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_delete", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_renew", kwargs={"pk": pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_suspend", kwargs={"pk": pk}), {"suspension_reason": "IDOR Suspend"}).status_code == 404


@pytest.mark.django_db
def test_trainingcompetency_idor_dossier_foreign_trainee(client_a, admin_user, admin_b):
    """Verify requesting Employee Training Dossier for Tenant B user safely falls back to caller."""
    url = reverse("quality:employee_training_dossier") + f"?trainee={admin_b.pk}"
    resp = client_a.get(url)
    assert resp.status_code == 200
    # Context must sanitize and NOT display admin_b
    assert resp.context["trainee"].pk != admin_b.pk
    assert resp.context["trainee"].pk == admin_user.pk


# ============================================================================
# 1B. CROSS-TENANT FOREIGN KEY INJECTION REJECTION
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_cross_tenant_fk_injection_matrix(client_a, quality_department_b):
    """Verify cross-tenant OrgUnit department injection in CompetencyMatrix is rejected."""
    data = {
        "title": "Cross-Tenant Injected Matrix",
        "role_title": "Injected Specialist",
        "qualification_tier": "independent",
        "department": quality_department_b.pk,
        "criticality": "high",
        "revision": "1.0",
        "minimum_passing_score": 80,
        "validity_period_months": 12,
        "prerequisite_experience_months": 3,
        "description": "Attempting cross-tenant FK injection.",
    }
    resp = client_a.post(reverse("quality:competency_matrix_create"), data)
    assert resp.status_code == 200
    assert "department" in resp.context["form"].errors


@pytest.mark.django_db
def test_trainingcompetency_cross_tenant_fk_injection_course(client_a, competency_matrix_b, quality_doc_b, admin_b):
    """Verify cross-tenant foreign key injection in QualityTrainingCourse is rejected."""
    data = {
        "title": "Cross-Tenant Injected Course",
        "competency_matrix": competency_matrix_b.pk,
        "course_code": "INJ-TRN-999",
        "category": "gxp_compliance",
        "delivery_method": "classroom_lecture",
        "assessment_method": "written_exam",
        "controlled_document": quality_doc_b.pk,
        "duration_hours": "3.00",
        "passing_score": 85,
        "instructor": admin_b.pk,
    }
    resp = client_a.post(reverse("quality:training_course_create"), data)
    assert resp.status_code == 200
    form_errors = resp.context["form"].errors
    assert "competency_matrix" in form_errors or "controlled_document" in form_errors or "instructor" in form_errors


@pytest.mark.django_db
def test_trainingcompetency_cross_tenant_fk_injection_enrollment(client_a, quality_course_b, admin_b):
    """Verify cross-tenant course and trainee injection in TrainingEnrollment is rejected."""
    today = timezone.now().date()
    data = {
        "course": quality_course_b.pk,
        "trainee": admin_b.pk,
        "assignment_reason": "annual_refresher",
        "assigned_date": today,
        "due_date": today + timedelta(days=30),
    }
    resp = client_a.post(reverse("quality:training_enrollment_create"), data)
    assert resp.status_code == 200
    form_errors = resp.context["form"].errors
    assert "course" in form_errors or "trainee" in form_errors


@pytest.mark.django_db
def test_trainingcompetency_cross_tenant_fk_injection_certification(client_a, training_enrollment_b, admin_b, quality_course_b, competency_matrix_b):
    """Verify cross-tenant enrollment, trainee, course, and matrix injection in CompetencyCertification is rejected."""
    today = timezone.now().date()
    data = {
        "enrollment": training_enrollment_b.pk,
        "trainee": admin_b.pk,
        "course": quality_course_b.pk,
        "competency_matrix": competency_matrix_b.pk,
        "qualification_title": "Cross-Tenant Injected Certification",
        "qualification_level": "level_2_qualified",
        "issue_date": today,
        "valid_until": today + timedelta(days=365),
        "renewal_interval_months": 12,
    }
    resp = client_a.post(reverse("quality:competency_certification_create"), data)
    assert resp.status_code == 200
    form_errors = resp.context["form"].errors
    assert any(k in form_errors for k in ("enrollment", "trainee", "course", "competency_matrix"))


# ============================================================================
# 2. AUTHENTICATION & AUTHORIZATION GATES (AuthN & AuthZ)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_anonymous_access_redirects(client, competency_matrix_a, quality_course_a, training_enrollment_a, competency_certification_a):
    """Verify unauthenticated requests to all 35 Training & Competency endpoints redirect to login."""
    m_pk = competency_matrix_a.pk
    c_pk = quality_course_a.pk
    e_pk = training_enrollment_a.pk
    cert_pk = competency_certification_a.pk

    urls = [
        # Competency Matrix
        reverse("quality:competency_matrix_list"),
        reverse("quality:competency_matrix_create"),
        reverse("quality:competency_matrix_export_csv"),
        reverse("quality:competency_matrix_detail", kwargs={"pk": m_pk}),
        reverse("quality:competency_matrix_edit", kwargs={"pk": m_pk}),
        reverse("quality:competency_matrix_delete", kwargs={"pk": m_pk}),
        reverse("quality:competency_matrix_approve", kwargs={"pk": m_pk}),
        reverse("quality:competency_matrix_retire", kwargs={"pk": m_pk}),
        # Training Course
        reverse("quality:training_course_list"),
        reverse("quality:training_course_create"),
        reverse("quality:training_course_export_csv"),
        reverse("quality:training_course_detail", kwargs={"pk": c_pk}),
        reverse("quality:training_course_edit", kwargs={"pk": c_pk}),
        reverse("quality:training_course_delete", kwargs={"pk": c_pk}),
        reverse("quality:training_course_activate", kwargs={"pk": c_pk}),
        reverse("quality:training_course_retire", kwargs={"pk": c_pk}),
        # Training Enrollment
        reverse("quality:training_enrollment_list"),
        reverse("quality:training_enrollment_create"),
        reverse("quality:training_enrollment_export_csv"),
        reverse("quality:training_enrollment_detail", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_edit", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_delete", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_complete", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_verify", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_waive", kwargs={"pk": e_pk}),
        # Competency Certification
        reverse("quality:competency_certification_list"),
        reverse("quality:competency_certification_create"),
        reverse("quality:competency_certification_export_csv"),
        reverse("quality:competency_certification_detail", kwargs={"pk": cert_pk}),
        reverse("quality:competency_certification_edit", kwargs={"pk": cert_pk}),
        reverse("quality:competency_certification_delete", kwargs={"pk": cert_pk}),
        reverse("quality:competency_certification_renew", kwargs={"pk": cert_pk}),
        reverse("quality:competency_certification_suspend", kwargs={"pk": cert_pk}),
        # Dashboards
        reverse("quality:training_compliance_dashboard"),
        reverse("quality:employee_training_dossier"),
    ]

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"URL {url} did not redirect (status {resp.status_code})"
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


@pytest.mark.django_db
def test_trainingcompetency_deletes_require_tenant_admin(member_client, competency_matrix_a, quality_course_a, training_enrollment_a, competency_certification_a):
    """Verify non-admin member cannot delete any Training & Competency entity (403 Forbidden)."""
    delete_urls = [
        reverse("quality:competency_matrix_delete", kwargs={"pk": competency_matrix_a.pk}),
        reverse("quality:training_course_delete", kwargs={"pk": quality_course_a.pk}),
        reverse("quality:training_enrollment_delete", kwargs={"pk": training_enrollment_a.pk}),
        reverse("quality:competency_certification_delete", kwargs={"pk": competency_certification_a.pk}),
    ]
    for url in delete_urls:
        resp = member_client.post(url)
        assert resp.status_code == 403, f"Delete URL {url} did not return 403 for non-admin (got {resp.status_code})"


@pytest.mark.django_db
def test_trainingcompetency_matrix_approve_role_gating(member_client, competency_matrix_a):
    """Verify standard non-admin member cannot approve competency matrix."""
    competency_matrix_a.status = "draft"
    competency_matrix_a.approved_by = None
    competency_matrix_a.save()

    url = reverse("quality:competency_matrix_approve", kwargs={"pk": competency_matrix_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    competency_matrix_a.refresh_from_db()
    assert competency_matrix_a.status == "draft"
    assert competency_matrix_a.approved_by is None


@pytest.mark.django_db
def test_trainingcompetency_matrix_retire_role_gating(member_client, competency_matrix_a):
    """Verify standard non-admin member cannot retire competency matrix."""
    competency_matrix_a.status = "approved"
    competency_matrix_a.save()

    url = reverse("quality:competency_matrix_retire", kwargs={"pk": competency_matrix_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    competency_matrix_a.refresh_from_db()
    assert competency_matrix_a.status == "approved"


@pytest.mark.django_db
def test_trainingcompetency_course_activate_role_gating(member_client, quality_course_a):
    """Verify standard non-admin member cannot activate training course."""
    quality_course_a.status = "draft"
    quality_course_a.save()

    url = reverse("quality:training_course_activate", kwargs={"pk": quality_course_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    quality_course_a.refresh_from_db()
    assert quality_course_a.status == "draft"


@pytest.mark.django_db
def test_trainingcompetency_course_retire_role_gating(member_client, quality_course_a):
    """Verify standard non-admin member cannot retire training course."""
    quality_course_a.status = "active"
    quality_course_a.save()

    url = reverse("quality:training_course_retire", kwargs={"pk": quality_course_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    quality_course_a.refresh_from_db()
    assert quality_course_a.status == "active"


@pytest.mark.django_db
def test_trainingcompetency_enrollment_waive_role_gating(member_client, training_enrollment_a):
    """Verify standard non-admin member cannot grant training waiver."""
    training_enrollment_a.status = "assigned"
    training_enrollment_a.waived_by = None
    training_enrollment_a.save()

    url = reverse("quality:training_enrollment_waive", kwargs={"pk": training_enrollment_a.pk})
    resp = member_client.post(url, {"waiver_reason": "Unauthorized waiver attempt"})
    assert resp.status_code == 302
    training_enrollment_a.refresh_from_db()
    assert training_enrollment_a.status == "assigned"
    assert training_enrollment_a.waived_by is None


@pytest.mark.django_db
def test_trainingcompetency_certification_renew_role_gating(member_client, competency_certification_a):
    """Verify standard non-admin member cannot renew competency certification."""
    original_expiry = competency_certification_a.valid_until
    url = reverse("quality:competency_certification_renew", kwargs={"pk": competency_certification_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    competency_certification_a.refresh_from_db()
    assert competency_certification_a.valid_until == original_expiry


@pytest.mark.django_db
def test_trainingcompetency_certification_suspend_role_gating(member_client, competency_certification_a):
    """Verify standard non-admin member cannot suspend competency certification."""
    competency_certification_a.status = "active"
    competency_certification_a.save()

    url = reverse("quality:competency_certification_suspend", kwargs={"pk": competency_certification_a.pk})
    resp = member_client.post(url, {"suspension_reason": "Unauthorized suspension attempt"})
    assert resp.status_code == 302
    competency_certification_a.refresh_from_db()
    assert competency_certification_a.status == "active"


# ============================================================================
# 3. SEGREGATION OF DUTIES (SoD) & EVALUATOR INDEPENDENCE
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_sod_trainee_cannot_verify_own_qualification(db, tenant_a, member_user, member_client, quality_course_a):
    """Verify that a trainee cannot self-verify their own practical qualification."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=member_user,
        assignment_reason="annual_refresher",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=25),
        status="completed",
        score=92,
        is_passed=True,
    )

    url = reverse("quality:training_enrollment_verify", kwargs={"pk": enrollment.pk})
    resp = member_client.post(
        url,
        {
            "practical_rating": "meets_standard",
            "practical_evaluation_notes": "Trainee self-evaluated proficiency.",
        },
    )
    assert resp.status_code == 302
    enrollment.refresh_from_db()
    assert enrollment.status == "completed"
    assert enrollment.practical_verified_by is None
    # Ensure no certification was auto-issued
    assert not CompetencyCertification.objects.filter(tenant=tenant_a, enrollment=enrollment).exists()


@pytest.mark.django_db
def test_trainingcompetency_sod_independent_supervisor_can_verify(db, tenant_a, member_user, client_a, admin_user, quality_course_a):
    """Verify an independent supervisor (admin_user) can verify trainee's practical demonstration."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=member_user,
        assignment_reason="role_transfer",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=25),
        status="completed",
        score=95,
        is_passed=True,
    )

    url = reverse("quality:training_enrollment_verify", kwargs={"pk": enrollment.pk})
    resp = client_a.post(
        url,
        {
            "practical_rating": "meets_standard",
            "practical_evaluation_notes": "Supervisor conducted independent gowning checklist verification.",
        },
    )
    assert resp.status_code == 302
    enrollment.refresh_from_db()
    assert enrollment.status == "verified"
    assert enrollment.practical_verified_by == admin_user
    # Certification must be auto-issued to trainee with supervisor as certifier
    cert = CompetencyCertification.objects.get(tenant=tenant_a, enrollment=enrollment)
    assert cert.trainee == member_user
    assert cert.certified_by == admin_user
    assert cert.status == "active"
    assert cert.certificate_hash is not None


# ============================================================================
# 4. MASS ASSIGNMENT & FIELD IMMUTABILITY
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_mass_assignment_matrix(client_a, quality_department):
    """Verify manipulated status and number in POST cannot bypass draft workflow or force numbers."""
    data = {
        "title": "Cleanroom Gowning Matrix",
        "role_title": "Cleanroom Operator",
        "qualification_tier": "independent",
        "department": quality_department.pk,
        "criticality": "critical_gxp",
        "revision": "1.0",
        "minimum_passing_score": 80,
        "validity_period_months": 12,
        "prerequisite_experience_months": 0,
        "status": "approved",  # Manipulated field
        "number": "CUSTOM-MTX-001",  # Manipulated field
    }
    resp = client_a.post(reverse("quality:competency_matrix_create"), data)
    assert resp.status_code == 302
    matrix = CompetencyMatrix.objects.get(title="Cleanroom Gowning Matrix")
    # Must be draft and auto-numbered
    assert matrix.status == "draft"
    assert matrix.number.startswith("QMTX-")
    assert matrix.number != "CUSTOM-MTX-001"


@pytest.mark.django_db
def test_trainingcompetency_mass_assignment_course(client_a, competency_matrix_a):
    """Verify manipulated status and number in course form cannot force active status or custom number."""
    data = {
        "title": "Bioburden Testing SOP Course",
        "competency_matrix": competency_matrix_a.pk,
        "course_code": "BIO-TRN-001",
        "category": "gxp_compliance",
        "delivery_method": "classroom_lecture",
        "assessment_method": "written_exam",
        "duration_hours": "1.50",
        "passing_score": 80,
        "status": "active",  # Manipulated field
        "number": "CUSTOM-CRSE-999",  # Manipulated field
    }
    resp = client_a.post(reverse("quality:training_course_create"), data)
    assert resp.status_code == 302
    course = QualityTrainingCourse.objects.get(title="Bioburden Testing SOP Course")
    assert course.status == "draft"
    assert course.number.startswith("QCRS-")
    assert course.number != "CUSTOM-CRSE-999"


@pytest.mark.django_db
def test_trainingcompetency_mass_assignment_enrollment(client_a, quality_course_a, member_user):
    """Verify manipulated status, score, and is_passed in enrollment form are ignored."""
    today = timezone.now().date()
    data = {
        "course": quality_course_a.pk,
        "trainee": member_user.pk,
        "assignment_reason": "annual_refresher",
        "assigned_date": today,
        "due_date": today + timedelta(days=30),
        "status": "verified",  # Manipulated field
        "score": 100,  # Manipulated field
        "is_passed": True,  # Manipulated field
        "number": "CUSTOM-ENR-777",  # Manipulated field
    }
    resp = client_a.post(reverse("quality:training_enrollment_create"), data)
    assert resp.status_code == 302
    enrollment = TrainingEnrollment.objects.get(course=quality_course_a, trainee=member_user, assignment_reason="annual_refresher")
    assert enrollment.status == "assigned"
    assert enrollment.score is None
    assert enrollment.is_passed is False
    assert enrollment.number.startswith("QENR-")
    assert enrollment.number != "CUSTOM-ENR-777"


@pytest.mark.django_db
def test_trainingcompetency_mass_assignment_certification(client_a, training_enrollment_a, admin_user, quality_course_a, competency_matrix_a):
    """Verify manipulated certificate_hash and number in certification form cannot tamper with security attributes."""
    today = timezone.now().date()
    data = {
        "enrollment": training_enrollment_a.pk,
        "trainee": admin_user.pk,
        "course": quality_course_a.pk,
        "competency_matrix": competency_matrix_a.pk,
        "qualification_title": "Certified Cleanroom Operator Level 2",
        "qualification_level": "level_2_qualified",
        "issue_date": today,
        "valid_until": today + timedelta(days=365),
        "renewal_interval_months": 12,
        "certificate_hash": "TAMPERED_INJECTED_HASH_999",  # Manipulated field
        "number": "CUSTOM-CERT-555",  # Manipulated field
    }
    resp = client_a.post(reverse("quality:competency_certification_create"), data)
    assert resp.status_code == 302
    cert = CompetencyCertification.objects.get(qualification_title="Certified Cleanroom Operator Level 2")
    assert cert.certificate_hash != "TAMPERED_INJECTED_HASH_999"
    assert len(cert.certificate_hash) == 64
    assert cert.number.startswith("QCERT-")
    assert cert.number != "CUSTOM-CERT-555"


# ============================================================================
# 5. REGULATORY INTEGRITY & EXAM SCORE GATING
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_exam_failure_gates_certification(client_a, training_enrollment_a):
    """Verify exam score below passing threshold marks enrollment failed and refuses certification."""
    training_enrollment_a.status = "assigned"
    training_enrollment_a.save()
    passing_threshold = training_enrollment_a.course.passing_score  # 80

    url = reverse("quality:training_enrollment_complete", kwargs={"pk": training_enrollment_a.pk})
    resp = client_a.post(
        url,
        {
            "score": passing_threshold - 5,  # 75% -> Failing score
            "notes": "Exam completed with deficiencies.",
            "status": "verified",  # Injected bypass attempt
            "is_passed": True,  # Injected bypass attempt
        },
    )
    assert resp.status_code == 302
    training_enrollment_a.refresh_from_db()
    assert training_enrollment_a.status == "failed"
    assert training_enrollment_a.is_passed is False
    assert training_enrollment_a.score == passing_threshold - 5
    # No certification issued
    assert not CompetencyCertification.objects.filter(enrollment=training_enrollment_a).exists()


@pytest.mark.django_db
def test_trainingcompetency_exam_pass_on_practical_course_halts_at_completed(client_a, training_enrollment_a):
    """Verify passing score on practical course stops at 'completed' awaiting hands-on assessment."""
    assert training_enrollment_a.course.assessment_method in ("both_exam_and_ojt", "practical_ojt")
    training_enrollment_a.status = "assigned"
    training_enrollment_a.save()

    url = reverse("quality:training_enrollment_complete", kwargs={"pk": training_enrollment_a.pk})
    resp = client_a.post(url, {"score": 90, "notes": "Written exam passed."})
    assert resp.status_code == 302
    training_enrollment_a.refresh_from_db()
    # Must be 'completed', NOT 'verified', because practical OJT is mandatory
    assert training_enrollment_a.status == "completed"
    assert training_enrollment_a.is_passed is True
    assert not CompetencyCertification.objects.filter(enrollment=training_enrollment_a).exists()


@pytest.mark.django_db
def test_trainingcompetency_exam_pass_on_exam_only_course_auto_issues_certification(db, tenant_a, client_a, admin_user, competency_matrix_a):
    """Verify passing exam on exam-only course auto-verifies and issues competency certification."""
    course = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="Written GMP Regulatory Principles",
        course_code="GMP-REG-101",
        category="gxp_compliance",
        delivery_method="elearning",
        assessment_method="written_exam",
        status="active",
        passing_score=80,
    )
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=course,
        trainee=admin_user,
        assignment_reason="new_hire",
        assigned_date=timezone.now().date(),
        due_date=timezone.now().date() + timedelta(days=14),
        status="assigned",
    )

    url = reverse("quality:training_enrollment_complete", kwargs={"pk": enrollment.pk})
    resp = client_a.post(url, {"score": 88})
    assert resp.status_code == 302
    enrollment.refresh_from_db()
    assert enrollment.status == "verified"
    assert enrollment.is_passed is True
    # Auto-issued certification
    cert = CompetencyCertification.objects.get(tenant=tenant_a, enrollment=enrollment)
    assert cert.trainee == admin_user
    assert cert.status == "active"
    assert cert.certificate_hash is not None


# ============================================================================
# 6. CSV FORMULA NEUTRALIZATION
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_csv_neutralization_matrix(client_a, tenant_a):
    """Verify CompetencyMatrix CSV export neutralizes spreadsheet formula injection (=, +, -, @)."""
    CompetencyMatrix.objects.create(
        tenant=tenant_a,
        title="=cmd|' /C calc'!A0",
        role_title="@SUM(1,9)",
        qualification_tier="independent",
        criticality="high",
        status="draft",
        revision="1.0",
        minimum_passing_score=80,
        validity_period_months=12,
    )

    resp = client_a.get(reverse("quality:competency_matrix_export_csv"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    content = resp.content.decode("utf-8")
    assert "'=cmd|' /C calc'!A0" in content
    assert "'@SUM(1,9)" in content


@pytest.mark.django_db
def test_trainingcompetency_csv_neutralization_course(client_a, tenant_a, competency_matrix_a):
    """Verify QualityTrainingCourse CSV export neutralizes formula injection."""
    QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="+2+5+cmd|' /C notepad'!A0",
        course_code="-HYPERLINK('http://malicious.com')",
        category="gxp_compliance",
        delivery_method="classroom_lecture",
        assessment_method="written_exam",
        duration_hours=Decimal("2.00"),
        passing_score=80,
        status="active",
    )

    resp = client_a.get(reverse("quality:training_course_export_csv"))
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "'+2+5+cmd|' /C notepad'!A0" in content
    assert "'-HYPERLINK('http://malicious.com')" in content


@pytest.mark.django_db
def test_trainingcompetency_csv_neutralization_enrollment(client_a, tenant_a, quality_course_a, training_enrollment_a):
    """Verify TrainingEnrollment CSV export neutralizes formula characters."""
    quality_course_a.title = "=1+1"
    quality_course_a.save()

    resp = client_a.get(reverse("quality:training_enrollment_export_csv"))
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "'=1+1" in content


@pytest.mark.django_db
def test_trainingcompetency_csv_neutralization_certification(client_a, tenant_a, training_enrollment_a, admin_user, quality_course_a, competency_matrix_a):
    """Verify CompetencyCertification CSV export neutralizes formula characters in title."""
    today = timezone.now().date()
    CompetencyCertification.objects.create(
        tenant=tenant_a,
        enrollment=training_enrollment_a,
        trainee=admin_user,
        course=quality_course_a,
        competency_matrix=competency_matrix_a,
        qualification_title="@EXEC('rmdir /S /Q C:\\')",
        qualification_level="level_2_qualified",
        issue_date=today,
        valid_until=today + timedelta(days=365),
        status="active",
        certified_by=admin_user,
    )

    resp = client_a.get(reverse("quality:competency_certification_export_csv"))
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "'@EXEC('rmdir /S /Q C:\\')" in content


# ============================================================================
# 7. STATE MACHINE LIFECYCLE GUARDS
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_state_machine_matrix_approve_invalid_state(client_a, competency_matrix_a):
    """Verify matrix can only be approved from draft status."""
    # 1. Already approved
    competency_matrix_a.status = "approved"
    competency_matrix_a.save()
    url = reverse("quality:competency_matrix_approve", kwargs={"pk": competency_matrix_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    # 2. Retired
    competency_matrix_a.status = "retired"
    competency_matrix_a.save()
    resp = client_a.post(url)
    assert resp.status_code == 302
    competency_matrix_a.refresh_from_db()
    assert competency_matrix_a.status == "retired"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_matrix_retire_invalid_state(client_a, competency_matrix_a):
    """Verify only approved matrix can be retired."""
    competency_matrix_a.status = "draft"
    competency_matrix_a.save()
    url = reverse("quality:competency_matrix_retire", kwargs={"pk": competency_matrix_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    competency_matrix_a.refresh_from_db()
    assert competency_matrix_a.status == "draft"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_course_activate_invalid_state(client_a, quality_course_a):
    """Verify course can only be activated from draft or under_revision."""
    # 1. Already active
    quality_course_a.status = "active"
    quality_course_a.save()
    url = reverse("quality:training_course_activate", kwargs={"pk": quality_course_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    # 2. Retired
    quality_course_a.status = "retired"
    quality_course_a.save()
    resp = client_a.post(url)
    assert resp.status_code == 302
    quality_course_a.refresh_from_db()
    assert quality_course_a.status == "retired"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_course_retire_invalid_state(client_a, quality_course_a):
    """Verify only active course can be retired."""
    quality_course_a.status = "draft"
    quality_course_a.save()
    url = reverse("quality:training_course_retire", kwargs={"pk": quality_course_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    quality_course_a.refresh_from_db()
    assert quality_course_a.status == "draft"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_enrollment_verify_non_completed(client_a, training_enrollment_a):
    """Verify verification is rejected if enrollment is not in 'completed' status."""
    training_enrollment_a.status = "assigned"
    training_enrollment_a.save()

    url = reverse("quality:training_enrollment_verify", kwargs={"pk": training_enrollment_a.pk})
    resp = client_a.post(url, {"practical_rating": "meets_standard"})
    assert resp.status_code == 302
    training_enrollment_a.refresh_from_db()
    assert training_enrollment_a.status == "assigned"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_enrollment_waive_invalid_state(client_a, training_enrollment_a):
    """Verify verified or already waived enrollments cannot be waived."""
    # 1. Already verified
    training_enrollment_a.status = "verified"
    training_enrollment_a.save()
    url = reverse("quality:training_enrollment_waive", kwargs={"pk": training_enrollment_a.pk})
    resp = client_a.post(url, {"waiver_reason": "Waive attempt on verified"})
    assert resp.status_code == 302
    training_enrollment_a.refresh_from_db()
    assert training_enrollment_a.status == "verified"

    # 2. Already waived
    training_enrollment_a.status = "waived"
    training_enrollment_a.save()
    resp = client_a.post(url, {"waiver_reason": "Duplicate waiver attempt"})
    assert resp.status_code == 302
    training_enrollment_a.refresh_from_db()
    assert training_enrollment_a.status == "waived"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_certification_renew_invalid_state(client_a, competency_certification_a):
    """Verify suspended or revoked certification cannot be renewed."""
    # 1. Suspended
    competency_certification_a.status = "suspended"
    competency_certification_a.save()
    url = reverse("quality:competency_certification_renew", kwargs={"pk": competency_certification_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    competency_certification_a.refresh_from_db()
    assert competency_certification_a.status == "suspended"

    # 2. Revoked
    competency_certification_a.status = "revoked"
    competency_certification_a.save()
    resp = client_a.post(url)
    assert resp.status_code == 302
    competency_certification_a.refresh_from_db()
    assert competency_certification_a.status == "revoked"


@pytest.mark.django_db
def test_trainingcompetency_state_machine_certification_suspend_invalid_state(client_a, competency_certification_a):
    """Verify already suspended or expired certification cannot be suspended."""
    # 1. Already suspended
    competency_certification_a.status = "suspended"
    competency_certification_a.save()
    url = reverse("quality:competency_certification_suspend", kwargs={"pk": competency_certification_a.pk})
    resp = client_a.post(url, {"suspension_reason": "Duplicate suspension"})
    assert resp.status_code == 302

    # 2. Expired
    competency_certification_a.status = "expired"
    competency_certification_a.save()
    resp = client_a.post(url, {"suspension_reason": "Suspension on expired"})
    assert resp.status_code == 302
    competency_certification_a.refresh_from_db()
    assert competency_certification_a.status == "expired"


# ============================================================================
# 8. HTTP METHOD RESTRICTIONS (@require_POST -> 405)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_action_methods_require_post(client_a, competency_matrix_a, quality_course_a, training_enrollment_a, competency_certification_a):
    """Verify all 13 mutation/action endpoints reject GET requests with 405 Method Not Allowed."""
    m_pk = competency_matrix_a.pk
    c_pk = quality_course_a.pk
    e_pk = training_enrollment_a.pk
    cert_pk = competency_certification_a.pk

    post_only_urls = [
        reverse("quality:competency_matrix_delete", kwargs={"pk": m_pk}),
        reverse("quality:competency_matrix_approve", kwargs={"pk": m_pk}),
        reverse("quality:competency_matrix_retire", kwargs={"pk": m_pk}),
        reverse("quality:training_course_delete", kwargs={"pk": c_pk}),
        reverse("quality:training_course_activate", kwargs={"pk": c_pk}),
        reverse("quality:training_course_retire", kwargs={"pk": c_pk}),
        reverse("quality:training_enrollment_delete", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_complete", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_verify", kwargs={"pk": e_pk}),
        reverse("quality:training_enrollment_waive", kwargs={"pk": e_pk}),
        reverse("quality:competency_certification_delete", kwargs={"pk": cert_pk}),
        reverse("quality:competency_certification_renew", kwargs={"pk": cert_pk}),
        reverse("quality:competency_certification_suspend", kwargs={"pk": cert_pk}),
    ]

    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"URL {url} did not return 405 on GET (got {resp.status_code})"
