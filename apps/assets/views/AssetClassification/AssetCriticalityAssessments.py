from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetClassification.AssetCriticalityAssessments import AssetCriticalityAssessmentForm
from apps.assets.models.AssetClassification.AssetCriticalityAssessments import AssetCriticalityAssessment
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_criticality_assessment_list(request):
    qs = AssetCriticalityAssessment.objects.filter(tenant=request.tenant).select_related(
        "asset__location", "assessor", "approved_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__number__icontains=q)
            | Q(asset__tag_code__icontains=q)
            | Q(findings_and_mitigation__icontains=q)
        )

    abc = request.GET.get("abc", "").strip()
    if abc:
        qs = qs.filter(abc_rating=abc)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(assessment_status=status)

    asset_id = request.GET.get("asset", "").strip()
    if asset_id and asset_id.isdigit():
        qs = qs.filter(asset_id=int(asset_id))

    # Aggregates for KPI cards
    all_assessments = AssetCriticalityAssessment.objects.filter(tenant=request.tenant)
    counts = all_assessments.aggregate(
        total=Count("id"),
        class_a=Count("id", filter=Q(abc_rating="A")),
        class_b=Count("id", filter=Q(abc_rating="B")),
        class_c=Count("id", filter=Q(abc_rating="C")),
        approved=Count("id", filter=Q(assessment_status="approved")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "assessments": page_obj,
        "assessment_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "abc_choices": AssetCriticalityAssessment.ABC_RATING_CHOICES,
        "status_choices": AssetCriticalityAssessment.STATUS_CHOICES,
        "q": q,
        "selected_abc": abc,
        "selected_status": status,
        "total_count": counts["total"] or 0,
        "class_a_count": counts["class_a"] or 0,
        "class_b_count": counts["class_b"] or 0,
        "class_c_count": counts["class_c"] or 0,
        "approved_count": counts["approved"] or 0,
    }
    return render(
        request, "assets/asset_classification/asset_criticality_assessment/list.html", context
    )


@login_required
def asset_criticality_assessment_detail(request, pk):
    assessment = assets_object(
        request,
        AssetCriticalityAssessment,
        pk=pk,
        select_related=["asset", "assessor", "approved_by"],
    )
    context = {
        "assessment": assessment,
    }
    return render(
        request, "assets/asset_classification/asset_criticality_assessment/detail.html", context
    )


@login_required
def asset_criticality_assessment_create(request):
    if request.method == "POST":
        form = AssetCriticalityAssessmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.tenant = request.tenant
            assessment.save()
            write_audit_log(request.user, assessment, "create", tenant=request.tenant)
            messages.success(
                request,
                f"Criticality Assessment {assessment.number} created (Score: {assessment.composite_score}, Tier: {assessment.get_abc_rating_display()}).",
            )
            return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
    else:
        form = AssetCriticalityAssessmentForm(tenant=request.tenant)

    context = {
        "form": form,
        "assessment": None,
        "is_edit": False,
    }
    return render(
        request, "assets/asset_classification/asset_criticality_assessment/form.html", context
    )


@login_required
def asset_criticality_assessment_edit(request, pk):
    assessment = assets_object(request, AssetCriticalityAssessment, pk=pk)
    if assessment.assessment_status in ("approved", "superseded"):
        messages.error(
            request,
            f"Assessment {assessment.number} is {assessment.get_assessment_status_display()} and cannot be edited.",
        )
        return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
    if request.method == "POST":
        form = AssetCriticalityAssessmentForm(request.POST, instance=assessment, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save()
            write_audit_log(request.user, assessment, "update", tenant=request.tenant)
            messages.success(
                request,
                f"Criticality Assessment {assessment.number} updated (Score: {assessment.composite_score}, Tier: {assessment.get_abc_rating_display()}).",
            )
            return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
    else:
        form = AssetCriticalityAssessmentForm(instance=assessment, tenant=request.tenant)

    context = {
        "form": form,
        "assessment": assessment,
        "is_edit": True,
    }
    return render(
        request, "assets/asset_classification/asset_criticality_assessment/form.html", context
    )


@login_required
@require_POST
@tenant_admin_required
def asset_criticality_assessment_delete(request, pk):
    assessment = assets_object(request, AssetCriticalityAssessment, pk=pk)
    if assessment.assessment_status in ("approved", "superseded"):
        messages.error(
            request,
            f"Assessment {assessment.number} cannot be deleted because it is {assessment.get_assessment_status_display()}.",
        )
        return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
    number = assessment.number
    write_audit_log(request.user, assessment, "delete", tenant=request.tenant)
    assessment.delete()
    messages.success(request, f"Criticality Assessment {number} deleted successfully.")
    return redirect("assets:asset_criticality_assessment_list")


@login_required
@require_POST
@tenant_admin_required
def asset_criticality_assessment_approve(request, pk):
    assessment = assets_object(request, AssetCriticalityAssessment, pk=pk, select_related=["asset"])
    if assessment.assessment_status == "approved":
        messages.info(request, f"Assessment {assessment.number} is already approved.")
        return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)

    with transaction.atomic():
        # Supersede any previous approved assessments for this exact physical asset
        AssetCriticalityAssessment.objects.filter(
            tenant=request.tenant,
            asset=assessment.asset,
            assessment_status="approved",
        ).exclude(pk=assessment.pk).update(assessment_status="superseded")

        assessment.assessment_status = "approved"
        assessment.approved_by = request.user
        assessment.approved_at = timezone.now()
        assessment.save()

        # Synchronize operational criticality on scm.Asset
        operational_criticality = "medium"
        if assessment.abc_rating == "A":
            operational_criticality = "critical"
        elif assessment.abc_rating == "B":
            operational_criticality = "high" if assessment.composite_score >= 16 else "medium"
        elif assessment.abc_rating == "C":
            operational_criticality = "low"

        assessment.asset.criticality = operational_criticality
        assessment.asset.save(update_fields=["criticality"])

        write_audit_log(request.user, assessment, "approve", tenant=request.tenant)

    messages.success(
        request,
        f"Criticality Assessment {assessment.number} approved! Synced operational criticality '{operational_criticality}' to Asset {assessment.asset.number}.",
    )
    return redirect("assets:asset_criticality_assessment_detail", pk=assessment.pk)
