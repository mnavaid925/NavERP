import csv
from datetime import timedelta
import hashlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.quality.forms.TrainingCompetency.TrainingEnrollments import (
    PracticalVerificationForm,
    TrainingCompletionForm,
    TrainingEnrollmentForm,
    TrainingWaiverForm,
)
from apps.quality.models.TrainingCompetency.CompetencyCertifications import CompetencyCertification
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log

User = get_user_model()


def _auto_issue_certification(enrollment, certifier, request):
    if not CompetencyCertification.objects.filter(tenant=request.tenant, enrollment=enrollment).exists():
        course = enrollment.course
        matrix = course.competency_matrix
        validity_months = matrix.validity_period_months if matrix else 12
        issue_date = timezone.now().date()
        valid_until = issue_date + timedelta(days=validity_months * 30)

        seed = f"{request.tenant.pk}:{enrollment.pk}:{enrollment.trainee.pk}:{issue_date}:{settings.SECRET_KEY}"
        cert_hash = hashlib.sha256(seed.encode()).hexdigest()

        cert = CompetencyCertification(
            tenant=request.tenant,
            enrollment=enrollment,
            trainee=enrollment.trainee,
            course=course,
            competency_matrix=matrix,
            qualification_title=f"{course.title} - Qualified Personnel",
            qualification_level="level_2_qualified",
            certificate_hash=cert_hash,
            issue_date=issue_date,
            valid_until=valid_until,
            renewal_interval_months=validity_months,
            status="active",
            certified_by=certifier,
            notes=f"Auto-issued upon qualification of enrollment {enrollment.number}.",
        )
        cert.save()
        write_audit_log(request.user, cert, "create", tenant=request.tenant)
        return cert
    return None


@login_required
def training_enrollment_list(request):
    qs = quality_scope(
        TrainingEnrollment.objects.select_related(
            "course", "trainee", "document_change_order", "capa_action", "practical_verified_by"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(course__title__icontains=q)
            | Q(number__icontains=q)
            | Q(trainee__first_name__icontains=q)
            | Q(trainee__last_name__icontains=q)
            | Q(trainee__username__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    reason = request.GET.get("assignment_reason", "").strip()
    if reason:
        qs = qs.filter(assignment_reason=reason)

    course_id = request.GET.get("course", "").strip()
    if course_id.isdigit():
        qs = qs.filter(course_id=int(course_id))

    trainee_id = request.GET.get("trainee", "").strip()
    if trainee_id.isdigit():
        qs = qs.filter(trainee_id=int(trainee_id))

    is_overdue = request.GET.get("is_overdue", "").strip()
    if is_overdue == "1":
        qs = qs.filter(status__in=["assigned", "in_progress"], due_date__lt=timezone.now().date())

    total_count = TrainingEnrollment.objects.filter(tenant=request.tenant).count()
    overdue_count = TrainingEnrollment.objects.filter(
        tenant=request.tenant, status__in=["assigned", "in_progress"], due_date__lt=timezone.now().date()
    ).count()
    verified_count = TrainingEnrollment.objects.filter(tenant=request.tenant, status="verified").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    courses = QualityTrainingCourse.objects.filter(tenant=request.tenant)
    trainees = User.objects.filter(tenant=request.tenant, is_active=True)

    context = {
        "enrollments": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "overdue_count": overdue_count,
        "verified_count": verified_count,
        "reason_choices": TrainingEnrollment.ASSIGNMENT_REASON_CHOICES,
        "status_choices": TrainingEnrollment.STATUS_CHOICES,
        "courses": courses,
        "trainees": trainees,
        "selected_status": status,
        "selected_reason": reason,
        "selected_course": course_id,
        "selected_trainee": trainee_id,
        "selected_overdue": is_overdue,
        "search_query": q,
    }
    return render(request, "quality/trainingcompetency/training_enrollment/list.html", context)


@login_required
def training_enrollment_detail(request, pk):
    enrollment = quality_object(
        request,
        TrainingEnrollment,
        pk,
        select_related=(
            "course", "course__competency_matrix", "course__controlled_document",
            "trainee", "document_change_order", "capa_action",
            "practical_verified_by", "waived_by"
        ),
        prefetch_related=("certifications",),
    )
    context = {
        "enrollment": enrollment,
        "obj": enrollment,
        "completion_form": TrainingCompletionForm(),
        "verification_form": PracticalVerificationForm(initial={"practical_rating": "meets_standard"}),
        "waiver_form": TrainingWaiverForm(),
        "certification": enrollment.certifications.filter(status="active").first(),
    }
    return render(request, "quality/trainingcompetency/training_enrollment/detail.html", context)


@login_required
def training_enrollment_create(request):
    if request.method == "POST":
        form = TrainingEnrollmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.tenant = request.tenant
            enrollment.save()
            write_audit_log(request.user, enrollment, "create", tenant=request.tenant)
            messages.success(request, f"Training Enrollment {enrollment.number} assigned successfully.")
            return redirect("quality:training_enrollment_detail", pk=enrollment.pk)
    else:
        initial = {
            "assigned_date": timezone.now().date(),
            "due_date": timezone.now().date() + timedelta(days=30),
        }
        course_id = request.GET.get("course", "").strip()
        if course_id.isdigit():
            initial["course"] = int(course_id)
        trainee_id = request.GET.get("trainee", "").strip()
        if trainee_id.isdigit():
            initial["trainee"] = int(trainee_id)
        form = TrainingEnrollmentForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "enrollment": None,
        "is_edit": False,
    }
    return render(request, "quality/trainingcompetency/training_enrollment/form.html", context)


@login_required
def training_enrollment_edit(request, pk):
    enrollment = quality_object(request, TrainingEnrollment, pk)
    if request.method == "POST":
        form = TrainingEnrollmentForm(request.POST, instance=enrollment, tenant=request.tenant)
        if form.is_valid():
            enrollment = form.save()
            write_audit_log(request.user, enrollment, "update", tenant=request.tenant)
            messages.success(request, f"Training Enrollment {enrollment.number} updated successfully.")
            return redirect("quality:training_enrollment_detail", pk=enrollment.pk)
    else:
        form = TrainingEnrollmentForm(instance=enrollment, tenant=request.tenant)

    context = {
        "form": form,
        "enrollment": enrollment,
        "obj": enrollment,
        "is_edit": True,
    }
    return render(request, "quality/trainingcompetency/training_enrollment/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def training_enrollment_delete(request, pk):
    enrollment = quality_object(request, TrainingEnrollment, pk)
    number = enrollment.number
    write_audit_log(request.user, enrollment, "delete", tenant=request.tenant)
    enrollment.delete()
    messages.success(request, f"Training Enrollment {number} deleted successfully.")
    return redirect("quality:training_enrollment_list")


@login_required
@require_POST
def training_enrollment_complete(request, pk):
    enrollment = quality_object(request, TrainingEnrollment, pk)
    form = TrainingCompletionForm(request.POST)
    if form.is_valid():
        score = form.cleaned_data.get("score")
        enrollment.self_certified = True
        enrollment.self_certified_at = timezone.now()
        enrollment.completion_date = timezone.now().date()
        if score is not None:
            enrollment.score = score
            enrollment.is_passed = score >= enrollment.course.passing_score
        else:
            enrollment.is_passed = True

        notes = form.cleaned_data.get("notes", "").strip()
        if notes:
            enrollment.notes = f"{enrollment.notes}\n[Completion Note]: {notes}".strip()

        # If exam score failed passing score, mark enrollment as failed
        if not enrollment.is_passed:
            enrollment.status = "failed"
            enrollment.save()
            write_audit_log(request.user, enrollment, "fail", tenant=request.tenant)
            messages.warning(
                request,
                f"Training score ({score}%) is below required passing score ({enrollment.course.passing_score}%). Enrollment marked failed.",
            )
            return redirect("quality:training_enrollment_detail", pk=enrollment.pk)

        # Check if practical evaluation is required
        if enrollment.course.assessment_method in ("practical_ojt", "both_exam_and_ojt"):
            enrollment.status = "completed"  # Pending practical evaluation
            enrollment.save()
            write_audit_log(request.user, enrollment, "complete", tenant=request.tenant)
            messages.success(request, f"Training completed. Awaiting supervisor practical OJT verification.")
        else:
            with transaction.atomic():
                enrollment.status = "verified"
                enrollment.save()
                write_audit_log(request.user, enrollment, "complete", tenant=request.tenant)
                _auto_issue_certification(enrollment, request.user, request)
            messages.success(request, f"Training completed and verified. Competency certification issued.")

    return redirect("quality:training_enrollment_detail", pk=enrollment.pk)


@login_required
@require_POST
def training_enrollment_verify(request, pk):
    enrollment = quality_object(request, TrainingEnrollment, pk)
    form = PracticalVerificationForm(request.POST)
    if form.is_valid():
        rating = form.cleaned_data.get("practical_rating")
        notes = form.cleaned_data.get("practical_evaluation_notes")
        enrollment.practical_rating = rating
        enrollment.practical_evaluation_notes = notes
        enrollment.practical_verified_by = request.user
        enrollment.practical_verified_at = timezone.now()

        if rating in ("exceeds_standard", "meets_standard"):
            with transaction.atomic():
                enrollment.status = "verified"
                enrollment.is_passed = True
                enrollment.save()
                write_audit_log(request.user, enrollment, "verify", tenant=request.tenant)
                _auto_issue_certification(enrollment, request.user, request)
            messages.success(request, f"Practical demonstration verified. Competency certification issued.")
        else:
            enrollment.status = "failed"
            enrollment.is_passed = False
            enrollment.save()
            write_audit_log(request.user, enrollment, "verify", tenant=request.tenant)
            messages.warning(request, f"Practical demonstration marked unsatisfactory. Qualification failed.")

    return redirect("quality:training_enrollment_detail", pk=enrollment.pk)


@login_required
@require_POST
def training_enrollment_waive(request, pk):
    enrollment = quality_object(request, TrainingEnrollment, pk)
    form = TrainingWaiverForm(request.POST)
    if form.is_valid():
        reason = form.cleaned_data.get("waiver_reason")
        enrollment.waiver_reason = reason
        enrollment.waived_by = request.user
        enrollment.waived_at = timezone.now()
        enrollment.status = "waived"
        enrollment.save()
        write_audit_log(request.user, enrollment, "waive", tenant=request.tenant)
        messages.success(request, f"Training enrollment {enrollment.number} has been formally waived.")

    return redirect("quality:training_enrollment_detail", pk=enrollment.pk)


@login_required
def training_enrollment_export_csv(request):
    qs = quality_scope(
        TrainingEnrollment.objects.select_related("course", "trainee", "practical_verified_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(course__title__icontains=q)
            | Q(number__icontains=q)
            | Q(trainee__username__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="training_enrollments.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Enrollment Number",
        "Course",
        "Trainee",
        "Assignment Reason",
        "Assigned Date",
        "Due Date",
        "Status",
        "Completion Date",
        "Score (%)",
        "Passed",
        "Practical Rating",
    ])

    for e in qs:
        writer.writerow([
            _csv_safe(e.number),
            _csv_safe(e.course.title),
            _csv_safe(e.trainee.get_full_name() or e.trainee.username),
            _csv_safe(e.get_assignment_reason_display()),
            _csv_safe(e.assigned_date),
            _csv_safe(e.due_date),
            _csv_safe(e.get_status_display()),
            _csv_safe(e.completion_date),
            _csv_safe(e.score),
            _csv_safe("Yes" if e.is_passed else "No"),
            _csv_safe(e.get_practical_rating_display() if e.practical_rating else ""),
        ])

    return response
