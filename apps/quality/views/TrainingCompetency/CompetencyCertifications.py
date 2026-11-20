import csv
from datetime import timedelta
import hashlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.quality.forms.TrainingCompetency.CompetencyCertifications import (
    CertificationSuspensionForm,
    CompetencyCertificationForm,
)
from apps.quality.models.TrainingCompetency.CompetencyCertifications import CompetencyCertification
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log

User = get_user_model()


@login_required
def competency_certification_list(request):
    qs = quality_scope(
        CompetencyCertification.objects.select_related(
            "trainee", "course", "competency_matrix", "certified_by", "enrollment"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(qualification_title__icontains=q)
            | Q(number__icontains=q)
            | Q(trainee__first_name__icontains=q)
            | Q(trainee__last_name__icontains=q)
            | Q(trainee__username__icontains=q)
            | Q(course__title__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    level = request.GET.get("qualification_level", "").strip()
    if level:
        qs = qs.filter(qualification_level=level)

    trainee_id = request.GET.get("trainee", "").strip()
    if trainee_id.isdigit():
        qs = qs.filter(trainee_id=int(trainee_id))

    course_id = request.GET.get("course", "").strip()
    if course_id.isdigit():
        qs = qs.filter(course_id=int(course_id))

    is_expiring = request.GET.get("expiring_soon", "").strip()
    today = timezone.now().date()
    if is_expiring == "1":
        qs = qs.filter(
            status="active",
            valid_until__gte=today,
            valid_until__lte=today + timedelta(days=30),
        )

    total_count = CompetencyCertification.objects.filter(tenant=request.tenant).count()
    active_count = CompetencyCertification.objects.filter(tenant=request.tenant, status="active").count()
    expiring_count = CompetencyCertification.objects.filter(
        tenant=request.tenant,
        status="active",
        valid_until__gte=today,
        valid_until__lte=today + timedelta(days=30),
    ).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    trainees = User.objects.filter(tenant=request.tenant, is_active=True)
    courses = QualityTrainingCourse.objects.filter(tenant=request.tenant)

    context = {
        "certifications": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "expiring_count": expiring_count,
        "level_choices": CompetencyCertification.QUALIFICATION_LEVEL_CHOICES,
        "status_choices": CompetencyCertification.STATUS_CHOICES,
        "trainees": trainees,
        "courses": courses,
        "selected_status": status,
        "selected_level": level,
        "selected_trainee": trainee_id,
        "selected_course": course_id,
        "selected_expiring": is_expiring,
        "search_query": q,
    }
    return render(request, "quality/trainingcompetency/competency_certification/list.html", context)


@login_required
def competency_certification_detail(request, pk):
    cert = quality_object(
        request,
        CompetencyCertification,
        pk,
        select_related=(
            "trainee", "course", "competency_matrix", "certified_by",
            "enrollment", "electronic_signature"
        ),
    )
    context = {
        "certification": cert,
        "obj": cert,
        "suspension_form": CertificationSuspensionForm(),
    }
    return render(request, "quality/trainingcompetency/competency_certification/detail.html", context)


@login_required
def competency_certification_create(request):
    if request.method == "POST":
        form = CompetencyCertificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cert = form.save(commit=False)
            cert.tenant = request.tenant
            if not getattr(cert, "certified_by_id", None):
                cert.certified_by = request.user
            cert.save()
            write_audit_log(request.user, cert, "create", tenant=request.tenant)
            messages.success(request, f"Competency Certification {cert.number} issued successfully.")
            return redirect("quality:competency_certification_detail", pk=cert.pk)
    else:
        initial = {
            "issue_date": timezone.now().date(),
            "valid_until": timezone.now().date() + timedelta(days=365),
        }
        trainee_id = request.GET.get("trainee", "").strip()
        if trainee_id.isdigit():
            initial["trainee"] = int(trainee_id)
        course_id = request.GET.get("course", "").strip()
        if course_id.isdigit():
            initial["course"] = int(course_id)
        form = CompetencyCertificationForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "certification": None,
        "is_edit": False,
    }
    return render(request, "quality/trainingcompetency/competency_certification/form.html", context)


@login_required
def competency_certification_edit(request, pk):
    cert = quality_object(request, CompetencyCertification, pk)
    if request.method == "POST":
        form = CompetencyCertificationForm(request.POST, instance=cert, tenant=request.tenant)
        if form.is_valid():
            cert = form.save()
            write_audit_log(request.user, cert, "update", tenant=request.tenant)
            messages.success(request, f"Competency Certification {cert.number} updated successfully.")
            return redirect("quality:competency_certification_detail", pk=cert.pk)
    else:
        form = CompetencyCertificationForm(instance=cert, tenant=request.tenant)

    context = {
        "form": form,
        "certification": cert,
        "obj": cert,
        "is_edit": True,
    }
    return render(request, "quality/trainingcompetency/competency_certification/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def competency_certification_delete(request, pk):
    cert = quality_object(request, CompetencyCertification, pk)
    number = cert.number
    write_audit_log(request.user, cert, "delete", tenant=request.tenant)
    cert.delete()
    messages.success(request, f"Competency Certification {number} deleted successfully.")
    return redirect("quality:competency_certification_list")


@login_required
@require_POST
def competency_certification_renew(request, pk):
    cert = quality_object(request, CompetencyCertification, pk)

    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)):
        messages.error(request, "Permission denied. Only authorized quality managers or tenant administrators can renew certifications.")
        return redirect("quality:competency_certification_detail", pk=cert.pk)

    if cert.status not in ("active", "expired", "expiring_soon"):
        messages.error(request, f"Certification in status '{cert.get_status_display()}' cannot be renewed.")
        return redirect("quality:competency_certification_detail", pk=cert.pk)

    today = timezone.now().date()
    interval_months = cert.renewal_interval_months or 12
    cert.issue_date = today
    cert.valid_until = today + timedelta(days=interval_months * 30)
    cert.status = "active"
    cert.certificate_hash = cert.generate_certificate_hash()
    cert.save()
    write_audit_log(request.user, cert, "renew", tenant=request.tenant)
    messages.success(request, f"Certification {cert.number} renewed until {cert.valid_until}.")
    return redirect("quality:competency_certification_detail", pk=cert.pk)


@login_required
@require_POST
def competency_certification_suspend(request, pk):
    cert = quality_object(request, CompetencyCertification, pk)

    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)):
        messages.error(request, "Permission denied. Only authorized quality managers or tenant administrators can suspend certifications.")
        return redirect("quality:competency_certification_detail", pk=cert.pk)

    if cert.status not in ("active", "expiring_soon"):
        messages.error(request, f"Only active certifications can be suspended.")
        return redirect("quality:competency_certification_detail", pk=cert.pk)

    form = CertificationSuspensionForm(request.POST)
    if form.is_valid():
        reason = form.cleaned_data.get("suspension_reason")
        cert.status = "suspended"
        cert.suspension_reason = reason
        cert.save()
        write_audit_log(request.user, cert, "suspend", tenant=request.tenant)
        messages.warning(request, f"Certification {cert.number} has been suspended.")

    return redirect("quality:competency_certification_detail", pk=cert.pk)


@login_required
def competency_certification_export_csv(request):
    qs = quality_scope(
        CompetencyCertification.objects.select_related("trainee", "course", "certified_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(qualification_title__icontains=q)
            | Q(number__icontains=q)
            | Q(trainee__username__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="competency_certifications.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Certificate Number",
        "Qualification Title",
        "Trainee",
        "Qualification Level",
        "Course",
        "Issue Date",
        "Valid Until",
        "Status",
        "Certified By",
        "Certificate Hash",
    ])

    for c in qs:
        writer.writerow([
            _csv_safe(c.number),
            _csv_safe(c.qualification_title),
            _csv_safe(c.trainee.get_full_name() or c.trainee.username),
            _csv_safe(c.get_qualification_level_display()),
            _csv_safe(c.course.title),
            _csv_safe(c.issue_date),
            _csv_safe(c.valid_until if c.valid_until else "Permanent"),
            _csv_safe(c.get_status_display()),
            _csv_safe(c.certified_by.get_full_name() or c.certified_by.username),
            _csv_safe(c.certificate_hash),
        ])

    return response


@login_required
def training_compliance_dashboard(request):
    tenant = request.tenant
    today = timezone.now().date()

    total_enrollments = TrainingEnrollment.objects.filter(tenant=tenant).count()
    verified_enrollments = TrainingEnrollment.objects.filter(tenant=tenant, status="verified").count()
    overdue_enrollments = TrainingEnrollment.objects.filter(
        tenant=tenant, status__in=["assigned", "in_progress"], due_date__lt=today
    ).count()

    compliance_rate = round((verified_enrollments / total_enrollments * 100), 1) if total_enrollments > 0 else 100.0

    active_certifications = CompetencyCertification.objects.filter(tenant=tenant, status="active").count()
    expiring_certifications = CompetencyCertification.objects.filter(
        tenant=tenant, status="active", valid_until__gte=today, valid_until__lte=today + timedelta(days=30)
    ).count()

    total_courses = QualityTrainingCourse.objects.filter(tenant=tenant).count()
    active_courses = QualityTrainingCourse.objects.filter(tenant=tenant, status="active").count()
    total_matrices = CompetencyMatrix.objects.filter(tenant=tenant).count()

    recent_enrollments = TrainingEnrollment.objects.filter(tenant=tenant).select_related(
        "course", "trainee"
    ).order_by("-created_at")[:8]

    expiring_list = CompetencyCertification.objects.filter(
        tenant=tenant, status="active", valid_until__gte=today, valid_until__lte=today + timedelta(days=30)
    ).select_related("trainee", "course").order_by("valid_until")[:6]

    # Department qualification breakdown consolidated into single aggregation query
    dept_rows = (
        TrainingEnrollment.objects.filter(
            tenant=tenant,
            course__competency_matrix__department__isnull=False,
        )
        .values(
            "course__competency_matrix__department__id",
            "course__competency_matrix__department__name",
        )
        .annotate(
            assigned=Count("id"),
            qualified=Count("id", filter=Q(status="verified")),
        )
        .order_by("-assigned")[:6]
    )
    dept_metrics = []
    for row in dept_rows:
        assigned = row["assigned"]
        qualified = row["qualified"]
        rate = round((qualified / assigned * 100), 1) if assigned > 0 else 100.0
        dept_metrics.append({
            "name": row["course__competency_matrix__department__name"],
            "assigned": assigned,
            "qualified": qualified,
            "rate": rate,
        })

    context = {
        "kpis": {
            "compliance_rate": compliance_rate,
            "total_enrollments": total_enrollments,
            "verified_enrollments": verified_enrollments,
            "overdue_enrollments": overdue_enrollments,
            "active_certifications": active_certifications,
            "expiring_certifications": expiring_certifications,
            "total_courses": total_courses,
            "active_courses": active_courses,
            "total_matrices": total_matrices,
        },
        "recent_enrollments": recent_enrollments,
        "expiring_list": expiring_list,
        "dept_metrics": dept_metrics,
        "department_metrics": dept_metrics,
        "active_certifications": active_certifications,
        "expiring_certifications": expiring_certifications,
    }
    return render(request, "quality/trainingcompetency/training_compliance_dashboard.html", context)


@login_required
def employee_training_dossier(request):
    tenant = request.tenant
    trainee_id = request.GET.get("trainee", "").strip()
    if trainee_id.isdigit():
        trainee = User.objects.filter(tenant=tenant, pk=int(trainee_id)).first()
    else:
        trainee = request.user

    if not trainee:
        trainee = request.user

    users = User.objects.filter(tenant=tenant, is_active=True)

    certifications = CompetencyCertification.objects.filter(tenant=tenant, trainee=trainee).select_related(
        "course", "competency_matrix", "certified_by"
    ).order_by("-issue_date")

    completed_enrollments = TrainingEnrollment.objects.filter(
        tenant=tenant, trainee=trainee, status__in=["verified", "completed", "waived"]
    ).select_related("course", "practical_verified_by").order_by("-completion_date")

    pending_enrollments = TrainingEnrollment.objects.filter(
        tenant=tenant, trainee=trainee, status__in=["assigned", "in_progress", "overdue"]
    ).select_related("course").order_by("due_date")

    total_assigned = TrainingEnrollment.objects.filter(tenant=tenant, trainee=trainee).count()
    completed_count = completed_enrollments.count()
    compliance_rate = round((completed_count / total_assigned * 100), 1) if total_assigned > 0 else 100.0
    active_certs_count = certifications.filter(status="active").count()

    context = {
        "trainee": trainee,
        "users": users,
        "certifications": certifications,
        "completed_enrollments": completed_enrollments,
        "pending_enrollments": pending_enrollments,
        "active_certifications": active_certs_count,
        "summary": {
            "total_assigned": total_assigned,
            "completed_count": completed_count,
            "pending_count": pending_enrollments.count(),
            "active_certs": active_certs_count,
            "active_certifications": active_certs_count,
            "compliance_rate": compliance_rate,
        },
    }
    return render(request, "quality/trainingcompetency/employee_training_dossier.html", context)
