"""Unit and functional view tests for Quality Management Sub-module 12.12: Training & Competency Management.

Covers:
1. Lists: competency_matrix_list, training_course_list, training_enrollment_list, competency_certification_list
   (search, filters, pagination, KPIs).
2. Creates (GET/POST): matrix, course, enrollment, certification.
3. Details (GET): matrix, course, enrollment (specifically asserting verified enrollment with
   practical_verified_by=None renders 200 without error), certification.
4. Edits (GET/POST): matrix, course, enrollment, certification.
5. Deletes (POST-only, tenant_admin_required): matrix, course, enrollment, certification.
6. Action / Lifecycle views:
   - competency_matrix_approve & competency_matrix_retire
   - training_course_activate & training_course_retire
   - training_enrollment_complete:
     * failing exam score (< passing_score) sets status to 'failed' and does NOT issue certification
     * passing exam score on non-practical course sets status to 'verified' and auto-issues certification
     * passing exam score on practical course sets status to 'completed'
   - training_enrollment_verify:
     * supervisor verification moves to 'verified' and auto-issues certification
     * unsatisfactory practical rating marks failed
     * trainee self-verification is blocked (SoD check)
   - training_enrollment_waive:
     * admin can waive enrollment with formal reason
   - competency_certification_renew:
     * renew extends validity and regenerates hash
   - competency_certification_suspend:
     * suspends active certification with reason
7. CSV exports: matrix, course, enrollment, certification export views return 200 with text/csv.
8. Dashboards: training_compliance_dashboard and employee_training_dossier (self and specific ?trainee=pk).
9. Cross-tenant isolation (IDOR protection returning 404).
"""
import csv
from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models.TrainingCompetency.CompetencyCertifications import CompetencyCertification
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment


def _trainingcompetency_relative_date(days: int) -> date:
    """Helper to return dates offset from today."""
    return timezone.now().date() + timedelta(days=days)


# ============================================================================
# 1. LIST VIEWS (search, filters, pagination, KPIs)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_list_view(client_a, competency_matrix_a, quality_department):
    """Verify CompetencyMatrix list returns 200, provides KPIs, search, and filters."""
    url = reverse("quality:competency_matrix_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "matrices" in resp.context
    assert "total_count" in resp.context
    assert "approved_count" in resp.context
    assert "active_count" in resp.context
    assert "paginator" in resp.context
    assert competency_matrix_a.title.encode() in resp.content

    # Search filter
    resp_q = client_a.get(url, {"q": "Cleanroom"})
    assert resp_q.status_code == 200
    assert competency_matrix_a.number.encode() in resp_q.content

    # Specific attribute filters
    resp_filter = client_a.get(
        url,
        {
            "status": "approved",
            "qualification_tier": "independent",
            "criticality": "critical_gxp",
            "department": str(quality_department.pk),
        },
    )
    assert resp_filter.status_code == 200
    assert competency_matrix_a.number.encode() in resp_filter.content


@pytest.mark.django_db
def test_trainingcompetency_course_list_view(client_a, quality_course_a, competency_matrix_a, quality_doc_effective):
    """Verify QualityTrainingCourse list returns 200, provides KPIs, search, and filters."""
    url = reverse("quality:training_course_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "courses" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "gxp_count" in resp.context
    assert quality_course_a.title.encode() in resp.content

    # Search filter
    resp_q = client_a.get(url, {"q": "Gowning"})
    assert resp_q.status_code == 200
    assert quality_course_a.course_code.encode() in resp_q.content

    # Dropdown filters
    resp_filter = client_a.get(
        url,
        {
            "category": "gxp_compliance",
            "delivery_method": "blended",
            "assessment_method": "both_exam_and_ojt",
            "status": "active",
            "competency_matrix": str(competency_matrix_a.pk),
            "controlled_document": str(quality_doc_effective.pk),
        },
    )
    assert resp_filter.status_code == 200
    assert quality_course_a.number.encode() in resp_filter.content


@pytest.mark.django_db
def test_trainingcompetency_enrollment_list_view(client_a, training_enrollment_a, quality_course_a, admin_user):
    """Verify TrainingEnrollment list returns 200, provides KPIs, search, and filters."""
    url = reverse("quality:training_enrollment_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "enrollments" in resp.context
    assert "total_count" in resp.context
    assert "overdue_count" in resp.context
    assert "verified_count" in resp.context
    assert training_enrollment_a.number.encode() in resp.content

    # Search filter
    resp_q = client_a.get(url, {"q": training_enrollment_a.number})
    assert resp_q.status_code == 200
    assert training_enrollment_a.number.encode() in resp_q.content

    # Filters by status, course, trainee, and overdue toggle
    resp_filter = client_a.get(
        url,
        {
            "status": "assigned",
            "assignment_reason": "annual_refresher",
            "course": str(quality_course_a.pk),
            "trainee": str(admin_user.pk),
            "is_overdue": "0",
        },
    )
    assert resp_filter.status_code == 200
    assert training_enrollment_a.number.encode() in resp_filter.content


@pytest.mark.django_db
def test_trainingcompetency_certification_list_view(
    client_a, competency_certification_a, admin_user, quality_course_a
):
    """Verify CompetencyCertification list returns 200, provides KPIs, search, and filters."""
    url = reverse("quality:competency_certification_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "certifications" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "expiring_count" in resp.context
    assert competency_certification_a.number.encode() in resp.content

    # Search filter
    resp_q = client_a.get(url, {"q": "Cleanroom"})
    assert resp_q.status_code == 200
    assert competency_certification_a.number.encode() in resp_q.content

    # Dropdown filters
    resp_filter = client_a.get(
        url,
        {
            "status": "active",
            "qualification_level": "level_2_qualified",
            "trainee": str(admin_user.pk),
            "course": str(quality_course_a.pk),
            "expiring_soon": "0",
        },
    )
    assert resp_filter.status_code == 200
    assert competency_certification_a.number.encode() in resp_filter.content


# ============================================================================
# 2. CREATE VIEWS (GET/POST)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_create_view(client_a, tenant_a, quality_department):
    """Verify CompetencyMatrix create GET and valid POST redirect to detail."""
    url = reverse("quality:competency_matrix_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    post_data = {
        "title": "Bio-Reactor Senior Specialist Matrix",
        "role_title": "Bio-Reactor Specialist",
        "qualification_tier": "specialist",
        "department": quality_department.pk,
        "criticality": "high",
        "revision": "1.0",
        "minimum_passing_score": 85,
        "validity_period_months": 24,
        "prerequisite_experience_months": 12,
        "description": "Qualifications for mammalian cell culture bioreactors.",
        "notes": "Annual requalification required.",
    }
    resp_post = client_a.post(url, post_data)
    assert resp_post.status_code == 302
    matrix = CompetencyMatrix.objects.filter(tenant=tenant_a, title=post_data["title"]).first()
    assert matrix is not None
    assert resp_post.url == reverse("quality:competency_matrix_detail", kwargs={"pk": matrix.pk})
    assert matrix.status == "draft"


@pytest.mark.django_db
def test_trainingcompetency_course_create_view(
    client_a, tenant_a, competency_matrix_a, quality_doc_effective, admin_user
):
    """Verify QualityTrainingCourse create GET and valid POST redirect to detail."""
    url = reverse("quality:training_course_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    post_data = {
        "title": "Freeze Dryer Chamber CIP/SIP Validation Course",
        "competency_matrix": competency_matrix_a.pk,
        "course_code": "TRN-CIP-009",
        "category": "equipment_operation",
        "delivery_method": "classroom_lecture",
        "assessment_method": "written_exam",
        "controlled_document": quality_doc_effective.pk,
        "document_revision": "Rev 1.0",
        "retrain_on_revision": True,
        "duration_hours": "3.50",
        "passing_score": 80,
        "ojt_checklist_criteria": "Chamber wash sequence check.",
        "syllabus_summary": "CIP/SIP protocols and validation parameters.",
        "instructor": admin_user.pk,
    }
    resp_post = client_a.post(url, post_data)
    assert resp_post.status_code == 302
    course = QualityTrainingCourse.objects.filter(tenant=tenant_a, course_code="TRN-CIP-009").first()
    assert course is not None
    assert resp_post.url == reverse("quality:training_course_detail", kwargs={"pk": course.pk})
    assert course.status == "draft"


@pytest.mark.django_db
def test_trainingcompetency_enrollment_create_view(client_a, tenant_a, quality_course_a, admin_user):
    """Verify TrainingEnrollment create GET (with query prefills) and valid POST."""
    url = reverse("quality:training_enrollment_create")
    resp_get = client_a.get(url, {"course": str(quality_course_a.pk), "trainee": str(admin_user.pk)})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    today = timezone.now().date()
    post_data = {
        "course": quality_course_a.pk,
        "trainee": admin_user.pk,
        "assignment_reason": "onboarding_new_hire",
        "assigned_date": today,
        "due_date": today + timedelta(days=20),
        "notes": "Initial cleanroom onboarding qualification.",
    }
    resp_post = client_a.post(url, post_data)
    assert resp_post.status_code == 302
    enrollment = TrainingEnrollment.objects.filter(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assignment_reason="onboarding_new_hire",
    ).first()
    assert enrollment is not None
    assert resp_post.url == reverse("quality:training_enrollment_detail", kwargs={"pk": enrollment.pk})
    assert enrollment.status == "assigned"


@pytest.mark.django_db
def test_trainingcompetency_certification_create_view(
    client_a, tenant_a, training_enrollment_a, quality_course_a, competency_matrix_a, admin_user
):
    """Verify CompetencyCertification create GET and valid POST auto-generating hash."""
    url = reverse("quality:competency_certification_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    today = timezone.now().date()
    post_data = {
        "enrollment": training_enrollment_a.pk,
        "trainee": admin_user.pk,
        "course": quality_course_a.pk,
        "competency_matrix": competency_matrix_a.pk,
        "qualification_title": "Directly Qualified Aseptic Operator",
        "qualification_level": "level_2_qualified",
        "issue_date": today,
        "valid_until": today + timedelta(days=365),
        "renewal_interval_months": 12,
        "authorized_work_centers": "Cleanroom Suite 1",
        "notes": "Issued under supervisory dispensation.",
    }
    resp_post = client_a.post(url, post_data)
    assert resp_post.status_code == 302
    cert = CompetencyCertification.objects.filter(
        tenant=tenant_a, qualification_title="Directly Qualified Aseptic Operator"
    ).first()
    assert cert is not None
    assert resp_post.url == reverse("quality:competency_certification_detail", kwargs={"pk": cert.pk})
    assert cert.certificate_hash != ""


# ============================================================================
# 3. DETAIL VIEWS (GET) & CRITICAL NULL CHECKS
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_detail_view(client_a, competency_matrix_a):
    """Verify CompetencyMatrix detail renders 200 and passes courses/certifications."""
    url = reverse("quality:competency_matrix_detail", kwargs={"pk": competency_matrix_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["matrix"] == competency_matrix_a
    assert resp.context["obj"] == competency_matrix_a
    assert "courses" in resp.context
    assert "certifications" in resp.context


@pytest.mark.django_db
def test_trainingcompetency_course_detail_view(client_a, quality_course_a):
    """Verify QualityTrainingCourse detail renders 200 and passes enrollments/certifications."""
    url = reverse("quality:training_course_detail", kwargs={"pk": quality_course_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["course"] == quality_course_a
    assert resp.context["obj"] == quality_course_a
    assert "recent_enrollments" in resp.context
    assert "active_enrollments" in resp.context
    assert "certifications" in resp.context


@pytest.mark.django_db
def test_trainingcompetency_enrollment_detail_view(client_a, training_enrollment_a):
    """Verify TrainingEnrollment detail renders 200 and provides action forms."""
    url = reverse("quality:training_enrollment_detail", kwargs={"pk": training_enrollment_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["enrollment"] == training_enrollment_a
    assert resp.context["obj"] == training_enrollment_a
    assert "completion_form" in resp.context
    assert "verification_form" in resp.context
    assert "waiver_form" in resp.context


@pytest.mark.django_db
def test_trainingcompetency_enrollment_detail_verified_with_null_verifier(
    client_a, tenant_a, quality_course_a, admin_user
):
    """Specifically assert verified enrollment with practical_verified_by=None renders 200 without error."""
    # When an exam-only course completes and auto-issues a cert, status is 'verified'
    # but practical_verified_by is None. The detail template must safely handle this.
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assignment_reason="annual_refresher",
        assigned_date=today - timedelta(days=10),
        due_date=today + timedelta(days=20),
        completion_date=today,
        status="verified",
        score=Decimal("95.00"),
        is_passed=True,
        practical_verified_by=None,
        practical_verified_at=None,
    )

    url = reverse("quality:training_enrollment_detail", kwargs={"pk": enrollment.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["enrollment"] == enrollment
    assert b"Verified" in resp.content


@pytest.mark.django_db
def test_trainingcompetency_certification_detail_view(client_a, competency_certification_a):
    """Verify CompetencyCertification detail renders 200 and passes suspension_form."""
    url = reverse("quality:competency_certification_detail", kwargs={"pk": competency_certification_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["certification"] == competency_certification_a
    assert resp.context["obj"] == competency_certification_a
    assert "suspension_form" in resp.context


# ============================================================================
# 4. EDIT VIEWS (GET/POST)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_edit_view(client_a, competency_matrix_a):
    """Verify CompetencyMatrix edit GET and POST updates record."""
    url = reverse("quality:competency_matrix_edit", kwargs={"pk": competency_matrix_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    update_data = {
        "title": "Aseptic Line Operator Matrix (Updated Edition)",
        "role_title": competency_matrix_a.role_title,
        "qualification_tier": competency_matrix_a.qualification_tier,
        "criticality": competency_matrix_a.criticality,
        "revision": "1.1",
        "minimum_passing_score": 85,
        "validity_period_months": 12,
        "prerequisite_experience_months": 8,
        "description": "Updated curriculum details.",
    }
    resp_post = client_a.post(url, update_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:competency_matrix_detail", kwargs={"pk": competency_matrix_a.pk})

    competency_matrix_a.refresh_from_db()
    assert competency_matrix_a.title == "Aseptic Line Operator Matrix (Updated Edition)"
    assert competency_matrix_a.revision == "1.1"
    assert competency_matrix_a.minimum_passing_score == 85


@pytest.mark.django_db
def test_trainingcompetency_course_edit_view(client_a, quality_course_a):
    """Verify QualityTrainingCourse edit GET and POST updates record."""
    url = reverse("quality:training_course_edit", kwargs={"pk": quality_course_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    update_data = {
        "title": "SOP-0042 Aseptic Gowning (Updated)",
        "competency_matrix": quality_course_a.competency_matrix_id,
        "course_code": quality_course_a.course_code,
        "category": quality_course_a.category,
        "delivery_method": quality_course_a.delivery_method,
        "assessment_method": quality_course_a.assessment_method,
        "duration_hours": "3.00",
        "passing_score": 85,
        "ojt_checklist_criteria": quality_course_a.ojt_checklist_criteria,
        "syllabus_summary": quality_course_a.syllabus_summary,
    }
    resp_post = client_a.post(url, update_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:training_course_detail", kwargs={"pk": quality_course_a.pk})

    quality_course_a.refresh_from_db()
    assert quality_course_a.title == "SOP-0042 Aseptic Gowning (Updated)"
    assert quality_course_a.duration_hours == Decimal("3.00")
    assert quality_course_a.passing_score == 85


@pytest.mark.django_db
def test_trainingcompetency_enrollment_edit_view(client_a, training_enrollment_a):
    """Verify TrainingEnrollment edit GET and POST updates record."""
    url = reverse("quality:training_enrollment_edit", kwargs={"pk": training_enrollment_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    new_due = _trainingcompetency_relative_date(45)
    update_data = {
        "course": training_enrollment_a.course_id,
        "trainee": training_enrollment_a.trainee_id,
        "assignment_reason": training_enrollment_a.assignment_reason,
        "assigned_date": training_enrollment_a.assigned_date,
        "due_date": new_due,
        "notes": "Extension approved by QA manager.",
    }
    resp_post = client_a.post(url, update_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:training_enrollment_detail", kwargs={"pk": training_enrollment_a.pk})

    training_enrollment_a.refresh_from_db()
    assert training_enrollment_a.due_date == new_due
    assert "Extension approved" in training_enrollment_a.notes


@pytest.mark.django_db
def test_trainingcompetency_certification_edit_view(client_a, competency_certification_a):
    """Verify CompetencyCertification edit GET and POST updates record."""
    url = reverse("quality:competency_certification_edit", kwargs={"pk": competency_certification_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    update_data = {
        "enrollment": competency_certification_a.enrollment_id,
        "trainee": competency_certification_a.trainee_id,
        "course": competency_certification_a.course_id,
        "competency_matrix": competency_certification_a.competency_matrix_id,
        "qualification_title": competency_certification_a.qualification_title,
        "qualification_level": competency_certification_a.qualification_level,
        "issue_date": competency_certification_a.issue_date,
        "valid_until": competency_certification_a.valid_until,
        "renewal_interval_months": competency_certification_a.renewal_interval_months,
        "authorized_work_centers": "Cleanroom Suite Alpha, Suite Beta, Fill Line 1 and 2",
        "notes": "Authorized for dual lines.",
    }
    resp_post = client_a.post(url, update_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:competency_certification_detail", kwargs={"pk": competency_certification_a.pk})

    competency_certification_a.refresh_from_db()
    assert "Suite Beta" in competency_certification_a.authorized_work_centers


# ============================================================================
# 5. DELETE VIEWS (POST-only, tenant_admin_required)
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_delete_view(client_a, tenant_a):
    """Verify CompetencyMatrix delete view rejects GET and deletes on POST."""
    matrix = CompetencyMatrix.objects.create(
        tenant=tenant_a,
        title="Temporary Delete Matrix",
        role_title="Temp Tech",
        qualification_tier="trainee",
        status="draft",
    )
    url = reverse("quality:competency_matrix_delete", kwargs={"pk": matrix.pk})

    # GET is rejected (require_POST)
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:competency_matrix_list")
    assert not CompetencyMatrix.objects.filter(pk=matrix.pk).exists()


@pytest.mark.django_db
def test_trainingcompetency_course_delete_view(client_a, tenant_a, competency_matrix_a):
    """Verify QualityTrainingCourse delete view rejects GET and deletes on POST."""
    course = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="Temporary Course To Delete",
        course_code="TEMP-DEL-01",
        category="quality_tools",
        delivery_method="elearning",
        assessment_method="attendance_only",
        status="draft",
    )
    url = reverse("quality:training_course_delete", kwargs={"pk": course.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:training_course_list")
    assert not QualityTrainingCourse.objects.filter(pk=course.pk).exists()


@pytest.mark.django_db
def test_trainingcompetency_enrollment_delete_view(client_a, tenant_a, quality_course_a, admin_user):
    """Verify TrainingEnrollment delete view rejects GET and deletes on POST."""
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assignment_reason="role_transfer",
        assigned_date=timezone.now().date(),
        due_date=timezone.now().date() + timedelta(days=10),
        status="assigned",
    )
    url = reverse("quality:training_enrollment_delete", kwargs={"pk": enrollment.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:training_enrollment_list")
    assert not TrainingEnrollment.objects.filter(pk=enrollment.pk).exists()


@pytest.mark.django_db
def test_trainingcompetency_certification_delete_view(client_a, tenant_a, quality_course_a, admin_user):
    """Verify CompetencyCertification delete view rejects GET and deletes on POST."""
    today = timezone.now().date()
    cert = CompetencyCertification(
        tenant=tenant_a,
        trainee=admin_user,
        course=quality_course_a,
        qualification_title="Temporary Cert to Delete",
        qualification_level="level_1_novice",
        certified_by=admin_user,
        issue_date=today,
        valid_until=today + timedelta(days=180),
        status="revoked",
    )
    cert.certificate_hash = cert.generate_certificate_hash()
    cert.save()

    url = reverse("quality:competency_certification_delete", kwargs={"pk": cert.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:competency_certification_list")
    assert not CompetencyCertification.objects.filter(pk=cert.pk).exists()


# ============================================================================
# 6. ACTION & LIFECYCLE WORKFLOWS
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_approve_and_retire(client_a, tenant_a, admin_user):
    """Verify matrix approval from draft and retirement from approved."""
    matrix = CompetencyMatrix.objects.create(
        tenant=tenant_a,
        title="Sterilization Validation Matrix",
        role_title="Validation Specialist",
        qualification_tier="specialist",
        status="draft",
    )
    approve_url = reverse("quality:competency_matrix_approve", kwargs={"pk": matrix.pk})
    retire_url = reverse("quality:competency_matrix_retire", kwargs={"pk": matrix.pk})

    # Cannot retire a draft matrix directly
    resp_retire_draft = client_a.post(retire_url)
    assert resp_retire_draft.status_code == 302
    matrix.refresh_from_db()
    assert matrix.status == "draft"

    # Approve draft
    resp_approve = client_a.post(approve_url)
    assert resp_approve.status_code == 302
    matrix.refresh_from_db()
    assert matrix.status == "approved"
    assert matrix.approved_by == admin_user
    assert matrix.approval_date == timezone.now().date()

    # Approving already approved matrix is rejected
    resp_reapprove = client_a.post(approve_url)
    assert resp_reapprove.status_code == 302

    # Retire approved matrix
    resp_retire = client_a.post(retire_url)
    assert resp_retire.status_code == 302
    matrix.refresh_from_db()
    assert matrix.status == "retired"


@pytest.mark.django_db
def test_trainingcompetency_course_activate_and_retire(client_a, tenant_a, competency_matrix_a):
    """Verify course activation from draft and retirement from active."""
    course = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="HEPA Filter Leak Testing Course",
        course_code="CRS-HEPA-001",
        category="technical_sop",
        delivery_method="classroom_lecture",
        assessment_method="written_exam",
        status="draft",
    )
    act_url = reverse("quality:training_course_activate", kwargs={"pk": course.pk})
    ret_url = reverse("quality:training_course_retire", kwargs={"pk": course.pk})

    # Activate
    resp_act = client_a.post(act_url)
    assert resp_act.status_code == 302
    course.refresh_from_db()
    assert course.status == "active"

    # Activating already active course fails
    resp_react = client_a.post(act_url)
    assert resp_react.status_code == 302

    # Retire
    resp_ret = client_a.post(ret_url)
    assert resp_ret.status_code == 302
    course.refresh_from_db()
    assert course.status == "retired"


@pytest.mark.django_db
def test_trainingcompetency_enrollment_complete_failing_score(client_a, tenant_a, quality_course_a, admin_user):
    """Test failing exam score (< passing_score) sets status to 'failed' and does NOT issue certification."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assignment_reason="annual_refresher",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=15),
        status="assigned",
    )
    url = reverse("quality:training_enrollment_complete", kwargs={"pk": enrollment.pk})

    # quality_course_a.passing_score is 80; score 65.00 fails
    resp = client_a.post(url, {"score": "65.00", "notes": "Failed aseptic gowning written section."})
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    assert enrollment.status == "failed"
    assert enrollment.is_passed is False
    assert enrollment.score == Decimal("65.00")
    assert enrollment.completion_date == today
    assert not CompetencyCertification.objects.filter(enrollment=enrollment).exists()


@pytest.mark.django_db
def test_trainingcompetency_enrollment_complete_non_practical_auto_cert(
    client_a, tenant_a, competency_matrix_a, admin_user
):
    """Test passing exam score on non-practical course sets status to 'verified' and auto-issues certification."""
    course_written = QualityTrainingCourse.objects.create(
        tenant=tenant_a,
        competency_matrix=competency_matrix_a,
        title="Good Documentation Practices (GDP) Exam",
        course_code="GDP-101",
        category="general",
        delivery_method="elearning",
        assessment_method="written_exam",  # Non-practical
        status="active",
        passing_score=80,
    )
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=course_written,
        trainee=admin_user,
        assignment_reason="annual_refresher",
        assigned_date=today - timedelta(days=3),
        due_date=today + timedelta(days=20),
        status="assigned",
    )
    url = reverse("quality:training_enrollment_complete", kwargs={"pk": enrollment.pk})

    resp = client_a.post(url, {"score": "95.00", "notes": "Scored 95% on online GDP exam."})
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    assert enrollment.status == "verified"
    assert enrollment.is_passed is True
    assert enrollment.score == Decimal("95.00")

    # Certification must be auto-issued
    cert = CompetencyCertification.objects.filter(enrollment=enrollment).first()
    assert cert is not None
    assert cert.status == "active"
    assert cert.trainee == admin_user
    assert cert.certificate_hash != ""


@pytest.mark.django_db
def test_trainingcompetency_enrollment_complete_practical_course_pending_ojt(
    client_a, tenant_a, quality_course_a, admin_user
):
    """Test passing exam score on practical course sets status to 'completed' without auto-issuing cert."""
    # quality_course_a assessment_method is "both_exam_and_ojt"
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assignment_reason="annual_refresher",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=15),
        status="assigned",
    )
    url = reverse("quality:training_enrollment_complete", kwargs={"pk": enrollment.pk})

    resp = client_a.post(url, {"score": "90.00", "notes": "Passed written test; practical observation needed."})
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    assert enrollment.status == "completed"  # Pending practical observation
    assert enrollment.is_passed is True
    assert not CompetencyCertification.objects.filter(enrollment=enrollment).exists()


@pytest.mark.django_db
def test_trainingcompetency_enrollment_verify_supervisor_issues_cert(
    client_a, tenant_a, quality_course_a, member_user, admin_user
):
    """Supervisor verification moves completed enrollment to 'verified' and auto-issues certification."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=member_user,
        assignment_reason="role_transfer",
        assigned_date=today - timedelta(days=10),
        due_date=today + timedelta(days=10),
        completion_date=today,
        status="completed",
        score=Decimal("92.00"),
        is_passed=True,
    )
    url = reverse("quality:training_enrollment_verify", kwargs={"pk": enrollment.pk})

    resp = client_a.post(
        url,
        {
            "practical_rating": "meets_standard",
            "practical_evaluation_notes": "Demonstrated sterile gowning without touching outer surfaces.",
        },
    )
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    assert enrollment.status == "verified"
    assert enrollment.practical_rating == "meets_standard"
    assert enrollment.practical_verified_by == admin_user
    assert enrollment.practical_verified_at is not None

    cert = CompetencyCertification.objects.filter(enrollment=enrollment).first()
    assert cert is not None
    assert cert.status == "active"
    assert cert.trainee == member_user


@pytest.mark.django_db
def test_trainingcompetency_enrollment_verify_unsatisfactory_fails(
    client_a, tenant_a, quality_course_a, member_user, admin_user
):
    """Unsatisfactory practical rating marks enrollment failed and does NOT issue certification."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=member_user,
        status="completed",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=5),
    )
    url = reverse("quality:training_enrollment_verify", kwargs={"pk": enrollment.pk})

    resp = client_a.post(
        url,
        {
            "practical_rating": "unsatisfactory",
            "practical_evaluation_notes": "Touched sterile gloves to unsterilized gown cart.",
        },
    )
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    assert enrollment.status == "failed"
    assert enrollment.is_passed is False
    assert not CompetencyCertification.objects.filter(enrollment=enrollment).exists()


@pytest.mark.django_db
def test_trainingcompetency_enrollment_verify_sod_trainee_blocked(
    member_client, tenant_a, quality_course_a, member_user
):
    """Test trainee self-verification is blocked by segregation of duties check."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=member_user,  # member_user is trainee
        assignment_reason="role_transfer",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=5),
        status="completed",
        score=Decimal("90.00"),
        is_passed=True,
    )
    url = reverse("quality:training_enrollment_verify", kwargs={"pk": enrollment.pk})

    # member_client (non-tenant-admin) attempts to verify their own practical qualification
    resp = member_client.post(
        url,
        {
            "practical_rating": "meets_standard",
            "practical_evaluation_notes": "Attempting self verification.",
        },
    )
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    # Status remains completed, not verified!
    assert enrollment.status == "completed"
    assert enrollment.practical_verified_by is None
    assert not CompetencyCertification.objects.filter(enrollment=enrollment).exists()


@pytest.mark.django_db
def test_trainingcompetency_enrollment_waive_admin(client_a, tenant_a, quality_course_a, admin_user):
    """Verify administrator can formally waive an enrollment with regulatory justification."""
    today = timezone.now().date()
    enrollment = TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=admin_user,
        assignment_reason="annual_refresher",
        assigned_date=today - timedelta(days=5),
        due_date=today + timedelta(days=15),
        status="assigned",
    )
    url = reverse("quality:training_enrollment_waive", kwargs={"pk": enrollment.pk})

    resp = client_a.post(
        url,
        {"waiver_reason": "Prior certified cleanroom master instructor credentials verified by QA director."},
    )
    assert resp.status_code == 302

    enrollment.refresh_from_db()
    assert enrollment.status == "waived"
    assert enrollment.waived_by == admin_user
    assert enrollment.waived_at is not None
    assert "cleanroom master instructor" in enrollment.waiver_reason


@pytest.mark.django_db
def test_trainingcompetency_certification_renew(client_a, competency_certification_a):
    """Verify certification renewal extends validity and updates the certificate hash."""
    url = reverse("quality:competency_certification_renew", kwargs={"pk": competency_certification_a.pk})
    old_valid_until = competency_certification_a.valid_until
    old_hash = competency_certification_a.certificate_hash

    # Fast forward: set to expired or expiring
    competency_certification_a.valid_until = timezone.now().date() - timedelta(days=1)
    competency_certification_a.status = "expired"
    competency_certification_a.save()

    resp = client_a.post(url)
    assert resp.status_code == 302

    competency_certification_a.refresh_from_db()
    assert competency_certification_a.status == "active"
    assert competency_certification_a.valid_until > old_valid_until
    assert competency_certification_a.certificate_hash != ""


@pytest.mark.django_db
def test_trainingcompetency_certification_suspend(client_a, competency_certification_a):
    """Verify active certification suspension with documented reason."""
    url = reverse("quality:competency_certification_suspend", kwargs={"pk": competency_certification_a.pk})

    resp = client_a.post(
        url,
        {"suspension_reason": "Major non-conformance NC-2026-088: contaminated gowning incident pending retraining."},
    )
    assert resp.status_code == 302

    competency_certification_a.refresh_from_db()
    assert competency_certification_a.status == "suspended"
    assert "NC-2026-088" in competency_certification_a.suspension_reason


# ============================================================================
# 7. CSV EXPORT VIEWS
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_matrix_export_csv(client_a, competency_matrix_a):
    """Verify CompetencyMatrix CSV export returns 200 with text/csv."""
    url = reverse("quality:competency_matrix_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert competency_matrix_a.number.encode() in resp.content


@pytest.mark.django_db
def test_trainingcompetency_course_export_csv(client_a, quality_course_a):
    """Verify QualityTrainingCourse CSV export returns 200 with text/csv."""
    url = reverse("quality:training_course_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert quality_course_a.course_code.encode() in resp.content


@pytest.mark.django_db
def test_trainingcompetency_enrollment_export_csv(client_a, training_enrollment_a):
    """Verify TrainingEnrollment CSV export returns 200 with text/csv."""
    url = reverse("quality:training_enrollment_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert training_enrollment_a.number.encode() in resp.content


@pytest.mark.django_db
def test_trainingcompetency_certification_export_csv(client_a, competency_certification_a):
    """Verify CompetencyCertification CSV export returns 200 with text/csv."""
    url = reverse("quality:competency_certification_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert competency_certification_a.number.encode() in resp.content


# ============================================================================
# 8. DASHBOARD & DOSSIER VIEWS
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_compliance_dashboard(
    client_a, competency_matrix_a, quality_course_a, training_enrollment_a, competency_certification_a
):
    """Verify training compliance dashboard returns 200 and passes required aggregations."""
    url = reverse("quality:training_compliance_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "kpis" in resp.context
    assert "compliance_rate" in resp.context["kpis"]
    assert "total_enrollments" in resp.context["kpis"]
    assert "verified_enrollments" in resp.context["kpis"]
    assert "active_certifications" in resp.context["kpis"]
    assert "recent_enrollments" in resp.context
    assert "expiring_list" in resp.context
    assert "dept_metrics" in resp.context


@pytest.mark.django_db
def test_trainingcompetency_employee_dossier_self(
    client_a, admin_user, training_enrollment_a, competency_certification_a
):
    """Verify employee training dossier default (self) view returns 200 with records."""
    url = reverse("quality:employee_training_dossier")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["trainee"] == admin_user
    assert "certifications" in resp.context
    assert "completed_enrollments" in resp.context
    assert "pending_enrollments" in resp.context
    assert "summary" in resp.context
    assert "compliance_rate" in resp.context["summary"]


@pytest.mark.django_db
def test_trainingcompetency_employee_dossier_specific_trainee(
    client_a, member_user, tenant_a, quality_course_a
):
    """Verify employee training dossier with ?trainee=pk loads specified user."""
    today = timezone.now().date()
    TrainingEnrollment.objects.create(
        tenant=tenant_a,
        course=quality_course_a,
        trainee=member_user,
        assignment_reason="role_transfer",
        assigned_date=today,
        due_date=today + timedelta(days=14),
        status="assigned",
    )
    url = reverse("quality:employee_training_dossier")
    resp = client_a.get(url, {"trainee": str(member_user.pk)})
    assert resp.status_code == 200
    assert resp.context["trainee"] == member_user
    assert resp.context["summary"]["total_assigned"] >= 1


# ============================================================================
# 9. CROSS-TENANT ISOLATION / IDOR PROTECTION
# ============================================================================

@pytest.mark.django_db
def test_trainingcompetency_cross_tenant_isolation(
    client_a,
    competency_matrix_b,
    quality_course_b,
    training_enrollment_b,
    competency_certification_b,
):
    """Verify Tenant A user receives 404 when attempting to access Tenant B objects."""
    # Matrix detail, edit, delete, actions
    assert client_a.get(reverse("quality:competency_matrix_detail", kwargs={"pk": competency_matrix_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:competency_matrix_edit", kwargs={"pk": competency_matrix_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_delete", kwargs={"pk": competency_matrix_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_approve", kwargs={"pk": competency_matrix_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_matrix_retire", kwargs={"pk": competency_matrix_b.pk})).status_code == 404

    # Course detail, edit, delete, actions
    assert client_a.get(reverse("quality:training_course_detail", kwargs={"pk": quality_course_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:training_course_edit", kwargs={"pk": quality_course_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_course_delete", kwargs={"pk": quality_course_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_course_activate", kwargs={"pk": quality_course_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_course_retire", kwargs={"pk": quality_course_b.pk})).status_code == 404

    # Enrollment detail, edit, delete, actions
    assert client_a.get(reverse("quality:training_enrollment_detail", kwargs={"pk": training_enrollment_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:training_enrollment_edit", kwargs={"pk": training_enrollment_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_delete", kwargs={"pk": training_enrollment_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_complete", kwargs={"pk": training_enrollment_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_verify", kwargs={"pk": training_enrollment_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:training_enrollment_waive", kwargs={"pk": training_enrollment_b.pk})).status_code == 404

    # Certification detail, edit, delete, actions
    assert client_a.get(reverse("quality:competency_certification_detail", kwargs={"pk": competency_certification_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:competency_certification_edit", kwargs={"pk": competency_certification_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_delete", kwargs={"pk": competency_certification_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_renew", kwargs={"pk": competency_certification_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:competency_certification_suspend", kwargs={"pk": competency_certification_b.pk})).status_code == 404
