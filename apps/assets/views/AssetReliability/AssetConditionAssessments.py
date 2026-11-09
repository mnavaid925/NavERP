from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetReliability.AssetConditionAssessments import AssetConditionAssessmentForm
from apps.assets.models import AssetCategory, AssetMaintenanceRequest
from apps.assets.models.AssetReliability.AssetConditionAssessments import AssetConditionAssessment
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_condition_assessment_list(request):
    qs = assets_scope(
        AssetConditionAssessment.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "inspector",
            "external_inspector",
            "triggered_maintenance_request",
        ),
        request,
    )

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(findings__icontains=q)
            | Q(fixed_asset__asset_number__icontains=q)
            | Q(operational_asset__asset_tag__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    grade_filter = request.GET.get("condition_grade", "").strip()
    if grade_filter:
        qs = qs.filter(condition_grade=grade_filter)

    type_filter = request.GET.get("assessment_type", "").strip()
    if type_filter:
        qs = qs.filter(assessment_type=type_filter)

    op_status_filter = request.GET.get("operating_status", "").strip()
    if op_status_filter:
        qs = qs.filter(operating_status=op_status_filter)

    cat_filter = request.GET.get("category", "").strip()
    if cat_filter:
        qs = qs.filter(asset_category_id=cat_filter)

    # Aggregates / Stats over tenant base
    tenant_base = AssetConditionAssessment.objects.filter(tenant=request.tenant)
    total_assessments = tenant_base.count()
    critical_defect_count = tenant_base.filter(condition_grade__in=["grade_4_poor", "grade_5_critical"]).count()
    avg_score = tenant_base.aggregate(avg=Avg("health_score"))["avg"]
    average_health_score = round(avg_score, 1) if avg_score is not None else 0.0
    followup_count = tenant_base.filter(followup_required=True).count()

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "condition_assessments": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetConditionAssessment.STATUS_CHOICES,
        "condition_grade_choices": AssetConditionAssessment.CONDITION_GRADE_CHOICES,
        "assessment_type_choices": AssetConditionAssessment.ASSESSMENT_TYPE_CHOICES,
        "operating_status_choices": AssetConditionAssessment.OPERATING_STATUS_CHOICES,
        "category_list": AssetCategory.objects.filter(tenant=request.tenant),
        "total_assessments": total_assessments,
        "critical_defect_count": critical_defect_count,
        "average_health_score": average_health_score,
        "followup_count": followup_count,
    }
    return render(request, "assets/assetreliability/asset_condition_assessment/list.html", context)


@login_required
def asset_condition_assessment_detail(request, pk):
    assessment = assets_object(
        request,
        AssetConditionAssessment,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "inspector",
            "external_inspector",
            "reviewed_by",
            "triggered_maintenance_request",
        ],
    )
    return render(
        request,
        "assets/assetreliability/asset_condition_assessment/detail.html",
        {"assessment": assessment},
    )


@login_required
def asset_condition_assessment_create(request):
    if request.method == "POST":
        form = AssetConditionAssessmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.tenant = request.tenant
            if not assessment.inspector and not assessment.external_inspector:
                assessment.inspector = request.user
            assessment.save()
            write_audit_log(request.user, assessment, "create", tenant=request.tenant)
            messages.success(request, f"Condition Assessment {assessment.number} created successfully.")
            return redirect("assets:asset_condition_assessment_detail", pk=assessment.pk)
    else:
        initial = {"assessment_date": timezone.now().date()}
        form = AssetConditionAssessmentForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/assetreliability/asset_condition_assessment/form.html",
        {"form": form, "assessment": None, "is_edit": False},
    )


@login_required
def asset_condition_assessment_edit(request, pk):
    assessment = assets_object(request, AssetConditionAssessment, pk)
    if request.method == "POST":
        form = AssetConditionAssessmentForm(request.POST, instance=assessment, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save()
            write_audit_log(request.user, assessment, "update", tenant=request.tenant)
            messages.success(request, f"Condition Assessment {assessment.number} updated successfully.")
            return redirect("assets:asset_condition_assessment_detail", pk=assessment.pk)
    else:
        form = AssetConditionAssessmentForm(instance=assessment, tenant=request.tenant)

    return render(
        request,
        "assets/assetreliability/asset_condition_assessment/form.html",
        {"form": form, "assessment": assessment, "is_edit": True},
    )


@login_required
@require_POST
def asset_condition_assessment_delete(request, pk):
    assessment = assets_object(request, AssetConditionAssessment, pk)
    number = assessment.number
    write_audit_log(request.user, assessment, "delete", tenant=request.tenant)
    assessment.delete()
    messages.success(request, f"Condition Assessment {number} deleted successfully.")
    return redirect("assets:asset_condition_assessment_list")


@login_required
@require_POST
def asset_condition_assessment_complete(request, pk):
    assessment = assets_object(request, AssetConditionAssessment, pk)
    if assessment.status == "draft":
        assessment.status = "completed"
        assessment.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, assessment, "update", tenant=request.tenant)
        messages.success(request, f"Assessment {assessment.number} marked as Completed.")
    return redirect("assets:asset_condition_assessment_detail", pk=assessment.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_condition_assessment_review(request, pk):
    assessment = assets_object(request, AssetConditionAssessment, pk)
    if assessment.status in ["draft", "completed"]:
        assessment.status = "reviewed"
        assessment.reviewed_by = request.user
        assessment.reviewed_at = timezone.now()
        assessment.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        write_audit_log(request.user, assessment, "update", tenant=request.tenant)
        messages.success(request, f"Assessment {assessment.number} approved and reviewed.")
    return redirect("assets:asset_condition_assessment_detail", pk=assessment.pk)


@login_required
@require_POST
def asset_condition_assessment_trigger_request(request, pk):
    assessment = assets_object(request, AssetConditionAssessment, pk)
    if assessment.triggered_maintenance_request:
        messages.info(request, f"Maintenance Request {assessment.triggered_maintenance_request.number} already created.")
        return redirect("assets:asset_maintenance_request_detail", pk=assessment.triggered_maintenance_request.pk)

    # Dynamic urgency mapping based on condition grade
    urgency_map = {
        "grade_5_critical": "critical",
        "grade_4_poor": "high",
        "grade_3_fair": "medium",
        "grade_2_good": "low",
        "grade_1_excellent": "low",
    }
    urgency = urgency_map.get(assessment.condition_grade, "medium")
    is_breakdown = assessment.operating_status in ["quarantined_unsafe", "decommission_recommended"]

    req = AssetMaintenanceRequest.objects.create(
        tenant=request.tenant,
        title=f"Corrective Repair - {assessment.title[:180]}",
        fixed_asset=assessment.fixed_asset,
        operational_asset=assessment.operational_asset,
        requester=request.user,
        request_type="preventive_inspection" if assessment.condition_grade in ["grade_1_excellent", "grade_2_good"] else "breakdown_repair",
        urgency=urgency,
        is_breakdown=is_breakdown,
        symptom_description=f"Automated maintenance ticket triggered from Condition Assessment {assessment.number}.\nFindings: {assessment.findings}\nRecommendations: {assessment.recommendations}",
    )
    assessment.triggered_maintenance_request = req
    assessment.followup_required = True
    assessment.save(update_fields=["triggered_maintenance_request", "followup_required", "updated_at"])
    write_audit_log(request.user, assessment, "update", tenant=request.tenant)
    write_audit_log(request.user, req, "create", tenant=request.tenant)

    messages.success(request, f"Created Maintenance Request {req.number} from Assessment {assessment.number}.")
    return redirect("assets:asset_maintenance_request_detail", pk=req.pk)
