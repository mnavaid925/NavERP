from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.DataIntegrity.DataIntegrityAssessments import DataIntegrityAssessmentForm
from apps.quality.models.DataIntegrity.DataIntegrityAssessments import DataIntegrityAssessment
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 20


@login_required
def data_integrity_assessment_list(request):
    base_qs = quality_scope(
        DataIntegrityAssessment.objects.all(),
        request,
    )

    stats = base_qs.aggregate(
        total=Count("id"),
        high_risk=Count("id", filter=Q(overall_risk_level__in=["high", "critical"])),
        remediation_pending=Count("id", filter=Q(status="remediation_pending")),
        approved=Count("id", filter=Q(status="approved")),
    )
    total_count = stats["total"]
    high_risk_count = stats["high_risk"]
    pending_remediation_count = stats["remediation_pending"]
    approved_count = stats["approved"]

    qs = base_qs.select_related("system", "org_unit", "lead_assessor", "qa_reviewer")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(assessment_scope__icontains=q)
            | Q(vulnerabilities_summary__icontains=q)
        )

    risk_selected = request.GET.get("risk_level", "").strip()
    if risk_selected:
        qs = qs.filter(overall_risk_level=risk_selected)

    status_selected = request.GET.get("status", "").strip()
    if status_selected:
        qs = qs.filter(status=status_selected)

    system_selected = request.GET.get("system", "").strip()
    if system_selected.isdigit():
        qs = qs.filter(system_id=int(system_selected))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    systems = ComputerSystemValidation.objects.filter(
        tenant=request.tenant
    ).only("id", "system_name").order_by("system_name")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "assessments": page_obj.object_list,
        "total_count": total_count,
        "high_risk_count": high_risk_count,
        "pending_remediation_count": pending_remediation_count,
        "approved_count": approved_count,
        "risk_choices": DataIntegrityAssessment.RISK_LEVEL_CHOICES,
        "status_choices": DataIntegrityAssessment.STATUS_CHOICES,
        "systems": systems,
        "q": q,
        "risk_selected": risk_selected,
        "status_selected": status_selected,
        "system_selected": system_selected,
    }
    return render(
        request,
        "quality/data_integrity/data_integrity_assessment/list.html",
        context,
    )


@login_required
def data_integrity_assessment_detail(request, pk):
    assessment = quality_object(
        request,
        DataIntegrityAssessment,
        pk,
        select_related=("system", "org_unit", "lead_assessor", "qa_reviewer", "linked_capa", "linked_ncr"),
    )
    return render(
        request,
        "quality/data_integrity/data_integrity_assessment/detail.html",
        {"assessment": assessment},
    )


@login_required
def data_integrity_assessment_create(request):
    if request.method == "POST":
        form = DataIntegrityAssessmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                assessment = form.save(commit=False)
                assessment.tenant = request.tenant
                assessment.save()
                write_audit_log(request.user, assessment, "create", tenant=request.tenant)
            messages.success(request, f"Data Integrity Assessment {assessment.number} created successfully.")
            return redirect("quality:data_integrity_assessment_detail", pk=assessment.pk)
    else:
        form = DataIntegrityAssessmentForm(tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/data_integrity_assessment/form.html",
        {"form": form, "assessment": None, "is_edit": False},
    )


@login_required
def data_integrity_assessment_edit(request, pk):
    assessment = quality_object(request, DataIntegrityAssessment, pk)
    if request.method == "POST":
        form = DataIntegrityAssessmentForm(request.POST, instance=assessment, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                assessment = form.save()
                write_audit_log(request.user, assessment, "update", tenant=request.tenant)
            messages.success(request, f"Data Integrity Assessment {assessment.number} updated successfully.")
            return redirect("quality:data_integrity_assessment_detail", pk=assessment.pk)
    else:
        form = DataIntegrityAssessmentForm(instance=assessment, tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/data_integrity_assessment/form.html",
        {"form": form, "assessment": assessment, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def data_integrity_assessment_delete(request, pk):
    assessment = quality_object(request, DataIntegrityAssessment, pk)
    num = assessment.number
    with transaction.atomic():
        write_audit_log(request.user, assessment, "delete", tenant=request.tenant)
        assessment.delete()
    messages.success(request, f"Data Integrity Assessment {num} deleted.")
    return redirect("quality:data_integrity_assessment_list")
