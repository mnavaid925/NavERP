import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.RiskManagement.RiskAssessments import RiskAssessmentForm
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def risk_assessment_list(request):
    qs = quality_scope(RiskAssessment.objects.all(), request).select_related(
        "plan", "design_input"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(hazard_description__icontains=q)
            | Q(failure_mode__icontains=q)
            | Q(hazardous_situation__icontains=q)
            | Q(potential_harm__icontains=q)
        )

    selected_type = request.GET.get("analysis_type", "").strip()
    if selected_type:
        qs = qs.filter(analysis_type=selected_type)

    selected_cat = request.GET.get("hazard_category", "").strip()
    if selected_cat:
        qs = qs.filter(hazard_category=selected_cat)

    selected_level = request.GET.get("risk_level", "").strip()
    if selected_level:
        qs = qs.filter(initial_risk_level=selected_level)

    selected_status = request.GET.get("lifecycle_status", "").strip()
    if selected_status:
        qs = qs.filter(lifecycle_status=selected_status)

    selected_plan = request.GET.get("plan", "").strip()
    if selected_plan and selected_plan.isdigit():
        qs = qs.filter(plan_id=int(selected_plan))

    base_qs = quality_scope(RiskAssessment.objects.all(), request)
    total_count = base_qs.count()
    high_risk_count = base_qs.filter(initial_risk_level="unacceptable").count()
    unmitigated_count = base_qs.filter(residual_risk_acceptable=False).count()
    closed_count = base_qs.filter(lifecycle_status="closed").count()

    plans = quality_scope(RiskManagementPlan.objects.all(), request).order_by("number")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "quality/riskmanagement/risk_assessment/list.html",
        {
            "assessments": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "high_risk_count": high_risk_count,
            "unmitigated_count": unmitigated_count,
            "closed_count": closed_count,
            "analysis_type_choices": RiskAssessment.ANALYSIS_TYPE_CHOICES,
            "hazard_category_choices": RiskAssessment.HAZARD_CATEGORY_CHOICES,
            "risk_level_choices": RiskAssessment.RISK_LEVEL_CHOICES,
            "lifecycle_status_choices": RiskAssessment.LIFECYCLE_STATUS_CHOICES,
            "plans": plans,
            "selected_type": selected_type,
            "selected_cat": selected_cat,
            "selected_level": selected_level,
            "selected_status": selected_status,
            "selected_plan": selected_plan,
            "q": q,
        },
    )


@login_required
def risk_assessment_detail(request, pk):
    assessment = quality_object(
        request,
        RiskAssessment,
        pk,
        select_related=("plan", "design_input"),
    )
    control_measures = assessment.control_measures.select_related(
        "assigned_to", "design_input", "controlled_document", "design_verification"
    ).order_by("-created_at")

    return render(
        request,
        "quality/riskmanagement/risk_assessment/detail.html",
        {
            "assessment": assessment,
            "control_measures": control_measures,
        },
    )


@login_required
def risk_assessment_create(request):
    initial = {}
    plan_param = request.GET.get("plan", "").strip()
    if plan_param and plan_param.isdigit():
        initial["plan"] = int(plan_param)

    if request.method == "POST":
        form = RiskAssessmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.tenant = request.tenant
            assessment.save()
            write_audit_log(request.user, assessment, "create", tenant=request.tenant)
            messages.success(request, f"Risk Item {assessment.number} logged successfully.")
            return redirect("quality:risk_assessment_detail", pk=assessment.pk)
    else:
        form = RiskAssessmentForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_assessment/form.html",
        {
            "form": form,
            "assessment": None,
            "is_edit": False,
        },
    )


@login_required
def risk_assessment_edit(request, pk):
    assessment = quality_object(request, RiskAssessment, pk)
    if request.method == "POST":
        form = RiskAssessmentForm(request.POST, instance=assessment, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save()
            write_audit_log(request.user, assessment, "update", tenant=request.tenant)
            messages.success(request, f"Risk Item {assessment.number} updated successfully.")
            return redirect("quality:risk_assessment_detail", pk=assessment.pk)
    else:
        form = RiskAssessmentForm(instance=assessment, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_assessment/form.html",
        {
            "form": form,
            "assessment": assessment,
            "is_edit": True,
        },
    )


@require_POST
@login_required
def risk_assessment_delete(request, pk):
    assessment = quality_object(request, RiskAssessment, pk)
    number = assessment.number
    plan_id = assessment.plan_id
    assessment.delete()
    write_audit_log(request.user, assessment, "delete", tenant=request.tenant)
    messages.success(request, f"Risk Item {number} deleted successfully.")
    return redirect("quality:risk_management_plan_detail", pk=plan_id)


@login_required
def risk_assessment_export(request):
    qs = quality_scope(RiskAssessment.objects.all(), request).select_related(
        "plan", "design_input"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="risk_assessments.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Plan",
        "Analysis Type",
        "Hazard Category",
        "Hazard / Failure Mode",
        "Harm / Failure Effect",
        "Initial S",
        "Initial P",
        "Initial D",
        "Initial RPN",
        "Initial Risk Level",
        "Residual S",
        "Residual P",
        "Residual D",
        "Residual RPN",
        "Residual Risk Level",
        "Residual Risk Acceptable",
        "BRA Required",
        "Lifecycle Status",
        "Created At",
    ])

    for a in qs:
        writer.writerow([
            csv_safe(a.number),
            csv_safe(a.plan.number if a.plan else ""),
            csv_safe(a.get_analysis_type_display()),
            csv_safe(a.get_hazard_category_display()),
            csv_safe(a.hazard_description or a.failure_mode),
            csv_safe(a.potential_harm or a.failure_effect),
            a.initial_severity,
            a.initial_probability,
            a.initial_detectability,
            a.initial_rpn,
            csv_safe(a.get_initial_risk_level_display()),
            a.residual_severity or "",
            a.residual_probability or "",
            a.residual_detectability or "",
            a.residual_rpn or "",
            csv_safe(a.get_residual_risk_level_display() if a.residual_risk_level else ""),
            "Yes" if a.residual_risk_acceptable else "No",
            "Yes" if a.bra_required else "No",
            csv_safe(a.get_lifecycle_status_display()),
            csv_safe(a.created_at.strftime("%Y-%m-%d")),
        ])

    return response
