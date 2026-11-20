import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.quality.forms.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourseForm
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log


@login_required
def training_course_list(request):
    qs = quality_scope(
        QualityTrainingCourse.objects.select_related(
            "competency_matrix", "controlled_document", "external_provider", "instructor"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(course_code__icontains=q)
            | Q(syllabus_summary__icontains=q)
        )

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    delivery = request.GET.get("delivery_method", "").strip()
    if delivery:
        qs = qs.filter(delivery_method=delivery)

    assessment = request.GET.get("assessment_method", "").strip()
    if assessment:
        qs = qs.filter(assessment_method=assessment)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    matrix_id = request.GET.get("competency_matrix", "").strip()
    if matrix_id.isdigit():
        qs = qs.filter(competency_matrix_id=int(matrix_id))

    doc_id = request.GET.get("controlled_document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(controlled_document_id=int(doc_id))

    total_count = QualityTrainingCourse.objects.filter(tenant=request.tenant).count()
    active_count = QualityTrainingCourse.objects.filter(tenant=request.tenant, status="active").count()
    gxp_count = QualityTrainingCourse.objects.filter(tenant=request.tenant, category="gxp_compliance").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    matrices = CompetencyMatrix.objects.filter(tenant=request.tenant)
    documents = ControlledDocument.objects.filter(tenant=request.tenant)

    context = {
        "courses": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "gxp_count": gxp_count,
        "category_choices": QualityTrainingCourse.CATEGORY_CHOICES,
        "delivery_choices": QualityTrainingCourse.DELIVERY_METHOD_CHOICES,
        "assessment_choices": QualityTrainingCourse.ASSESSMENT_METHOD_CHOICES,
        "status_choices": QualityTrainingCourse.STATUS_CHOICES,
        "matrices": matrices,
        "documents": documents,
        "selected_category": category,
        "selected_delivery": delivery,
        "selected_assessment": assessment,
        "selected_status": status,
        "selected_matrix": matrix_id,
        "selected_doc": doc_id,
        "search_query": q,
    }
    return render(request, "quality/trainingcompetency/training_course/list.html", context)


@login_required
def training_course_detail(request, pk):
    course = quality_object(
        request,
        QualityTrainingCourse,
        pk,
        select_related=("competency_matrix", "controlled_document", "external_provider", "instructor"),
        prefetch_related=("enrollments", "enrollments__trainee", "issued_certifications"),
    )
    context = {
        "course": course,
        "obj": course,
        "recent_enrollments": course.enrollments.all()[:10],
        "active_enrollments": course.enrollments.filter(status__in=["assigned", "in_progress"]),
        "certifications": course.issued_certifications.filter(status="active"),
    }
    return render(request, "quality/trainingcompetency/training_course/detail.html", context)


@login_required
def training_course_create(request):
    if request.method == "POST":
        form = QualityTrainingCourseForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            course = form.save(commit=False)
            course.tenant = request.tenant
            course.save()
            write_audit_log(request.user, course, "create", tenant=request.tenant)
            messages.success(request, f"Training Course {course.number} created successfully.")
            return redirect("quality:training_course_detail", pk=course.pk)
    else:
        initial = {}
        matrix_id = request.GET.get("competency_matrix", "").strip()
        if matrix_id.isdigit():
            initial["competency_matrix"] = int(matrix_id)
        doc_id = request.GET.get("controlled_document", "").strip()
        if doc_id.isdigit():
            initial["controlled_document"] = int(doc_id)
        form = QualityTrainingCourseForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "course": None,
        "is_edit": False,
    }
    return render(request, "quality/trainingcompetency/training_course/form.html", context)


@login_required
def training_course_edit(request, pk):
    course = quality_object(request, QualityTrainingCourse, pk)
    if request.method == "POST":
        form = QualityTrainingCourseForm(request.POST, instance=course, tenant=request.tenant)
        if form.is_valid():
            course = form.save()
            write_audit_log(request.user, course, "update", tenant=request.tenant)
            messages.success(request, f"Training Course {course.number} updated successfully.")
            return redirect("quality:training_course_detail", pk=course.pk)
    else:
        form = QualityTrainingCourseForm(instance=course, tenant=request.tenant)

    context = {
        "form": form,
        "course": course,
        "obj": course,
        "is_edit": True,
    }
    return render(request, "quality/trainingcompetency/training_course/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def training_course_delete(request, pk):
    course = quality_object(request, QualityTrainingCourse, pk)
    number = course.number
    write_audit_log(request.user, course, "delete", tenant=request.tenant)
    course.delete()
    messages.success(request, f"Training Course {number} deleted successfully.")
    return redirect("quality:training_course_list")


@login_required
@require_POST
def training_course_activate(request, pk):
    course = quality_object(request, QualityTrainingCourse, pk)

    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)):
        messages.error(request, "Permission denied. Only authorized quality managers or tenant administrators can activate training courses.")
        return redirect("quality:training_course_detail", pk=course.pk)

    if course.status not in ("draft", "under_revision"):
        messages.error(request, f"Only draft or under-revision training courses can be activated (current status: {course.get_status_display()}).")
        return redirect("quality:training_course_detail", pk=course.pk)

    course.status = "active"
    course.save()
    write_audit_log(request.user, course, "activate", tenant=request.tenant)
    messages.success(request, f"Training Course {course.number} activated.")
    return redirect("quality:training_course_detail", pk=course.pk)


@login_required
@require_POST
def training_course_retire(request, pk):
    course = quality_object(request, QualityTrainingCourse, pk)

    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)):
        messages.error(request, "Permission denied. Only authorized quality managers or tenant administrators can retire training courses.")
        return redirect("quality:training_course_detail", pk=course.pk)

    if course.status != "active":
        messages.error(request, "Only active training courses can be retired.")
        return redirect("quality:training_course_detail", pk=course.pk)

    course.status = "retired"
    course.save()
    write_audit_log(request.user, course, "retire", tenant=request.tenant)
    messages.success(request, f"Training Course {course.number} retired.")
    return redirect("quality:training_course_detail", pk=course.pk)


@login_required
def training_course_export_csv(request):
    qs = quality_scope(
        QualityTrainingCourse.objects.select_related(
            "competency_matrix", "controlled_document", "external_provider", "instructor"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(course_code__icontains=q)
        )

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="training_courses.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Course Number",
        "Title",
        "Course Code",
        "Category",
        "Delivery Method",
        "Assessment Method",
        "Competency Matrix",
        "Bound SOP Document",
        "Duration (Hours)",
        "Passing Score",
        "Status",
    ])

    for c in qs:
        writer.writerow([
            _csv_safe(c.number),
            _csv_safe(c.title),
            _csv_safe(c.course_code),
            _csv_safe(c.get_category_display()),
            _csv_safe(c.get_delivery_method_display()),
            _csv_safe(c.get_assessment_method_display()),
            _csv_safe(c.competency_matrix.title if c.competency_matrix else ""),
            _csv_safe(c.controlled_document.number if c.controlled_document else ""),
            _csv_safe(c.duration_hours),
            _csv_safe(c.passing_score),
            _csv_safe(c.get_status_display()),
        ])

    return response
