import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.quality.forms.TrainingCompetency.CompetencyMatrices import CompetencyMatrixForm
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log


@login_required
def competency_matrix_list(request):
    qs = quality_scope(CompetencyMatrix.objects.select_related("department", "approved_by"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(role_title__icontains=q)
            | Q(description__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    tier = request.GET.get("qualification_tier", "").strip()
    if tier:
        qs = qs.filter(qualification_tier=tier)

    criticality = request.GET.get("criticality", "").strip()
    if criticality:
        qs = qs.filter(criticality=criticality)

    department_id = request.GET.get("department", "").strip()
    if department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    total_count = CompetencyMatrix.objects.filter(tenant=request.tenant).count()
    active_count = CompetencyMatrix.objects.filter(tenant=request.tenant, status="active").count()
    approved_count = CompetencyMatrix.objects.filter(tenant=request.tenant, status="approved").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant)

    context = {
        "matrices": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "approved_count": approved_count,
        "tier_choices": CompetencyMatrix.QUALIFICATION_TIER_CHOICES,
        "criticality_choices": CompetencyMatrix.CRITICALITY_CHOICES,
        "status_choices": CompetencyMatrix.STATUS_CHOICES,
        "departments": departments,
        "selected_status": status,
        "selected_tier": tier,
        "selected_criticality": criticality,
        "selected_department": department_id,
        "search_query": q,
    }
    return render(request, "quality/trainingcompetency/competency_matrix/list.html", context)


@login_required
def competency_matrix_detail(request, pk):
    matrix = quality_object(
        request,
        CompetencyMatrix,
        pk,
        select_related=("department", "approved_by"),
        prefetch_related=("courses", "courses__instructor", "certified_holders", "certified_holders__trainee"),
    )
    context = {
        "matrix": matrix,
        "obj": matrix,
        "courses": matrix.courses.all(),
        "certifications": matrix.certified_holders.filter(status="active"),
    }
    return render(request, "quality/trainingcompetency/competency_matrix/detail.html", context)


@login_required
def competency_matrix_create(request):
    if request.method == "POST":
        form = CompetencyMatrixForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            matrix = form.save(commit=False)
            matrix.tenant = request.tenant
            matrix.save()
            write_audit_log(request.user, matrix, "create", tenant=request.tenant)
            messages.success(request, f"Competency Matrix {matrix.number} created successfully.")
            return redirect("quality:competency_matrix_detail", pk=matrix.pk)
    else:
        form = CompetencyMatrixForm(tenant=request.tenant)

    context = {
        "form": form,
        "matrix": None,
        "is_edit": False,
    }
    return render(request, "quality/trainingcompetency/competency_matrix/form.html", context)


@login_required
def competency_matrix_edit(request, pk):
    matrix = quality_object(request, CompetencyMatrix, pk)
    if request.method == "POST":
        form = CompetencyMatrixForm(request.POST, instance=matrix, tenant=request.tenant)
        if form.is_valid():
            matrix = form.save()
            write_audit_log(request.user, matrix, "update", tenant=request.tenant)
            messages.success(request, f"Competency Matrix {matrix.number} updated successfully.")
            return redirect("quality:competency_matrix_detail", pk=matrix.pk)
    else:
        form = CompetencyMatrixForm(instance=matrix, tenant=request.tenant)

    context = {
        "form": form,
        "matrix": matrix,
        "obj": matrix,
        "is_edit": True,
    }
    return render(request, "quality/trainingcompetency/competency_matrix/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def competency_matrix_delete(request, pk):
    matrix = quality_object(request, CompetencyMatrix, pk)
    number = matrix.number
    write_audit_log(request.user, matrix, "delete", tenant=request.tenant)
    matrix.delete()
    messages.success(request, f"Competency Matrix {number} deleted successfully.")
    return redirect("quality:competency_matrix_list")


@login_required
@require_POST
def competency_matrix_approve(request, pk):
    matrix = quality_object(request, CompetencyMatrix, pk)
    matrix.status = "approved"
    matrix.approved_by = request.user
    matrix.approval_date = timezone.now().date()
    matrix.save()
    write_audit_log(request.user, matrix, "approve", tenant=request.tenant)
    messages.success(request, f"Competency Matrix {matrix.number} approved.")
    return redirect("quality:competency_matrix_detail", pk=matrix.pk)


@login_required
@require_POST
def competency_matrix_retire(request, pk):
    matrix = quality_object(request, CompetencyMatrix, pk)
    matrix.status = "retired"
    matrix.save()
    write_audit_log(request.user, matrix, "retire", tenant=request.tenant)
    messages.success(request, f"Competency Matrix {matrix.number} retired.")
    return redirect("quality:competency_matrix_detail", pk=matrix.pk)


@login_required
def competency_matrix_export_csv(request):
    qs = quality_scope(CompetencyMatrix.objects.select_related("department", "approved_by"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(role_title__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="competency_matrices.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Matrix Number",
        "Title",
        "Role Title",
        "Qualification Tier",
        "Department",
        "Criticality",
        "Revision",
        "Status",
        "Min Passing Score",
        "Validity Months",
    ])

    for m in qs:
        writer.writerow([
            _csv_safe(m.number),
            _csv_safe(m.title),
            _csv_safe(m.role_title),
            _csv_safe(m.get_qualification_tier_display()),
            _csv_safe(m.department.name if m.department else ""),
            _csv_safe(m.get_criticality_display()),
            _csv_safe(m.revision),
            _csv_safe(m.get_status_display()),
            _csv_safe(m.minimum_passing_score),
            _csv_safe(m.validity_period_months),
        ])

    return response
