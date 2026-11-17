import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.RiskManagement.RiskManagementPlans import RiskManagementPlanForm
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
def risk_management_plan_list(request):
    qs = quality_scope(RiskManagementPlan.objects.all(), request).select_related(
        "design_project", "lead_risk_manager", "department"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(scope_description__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_class = request.GET.get("device_class", "").strip()
    if selected_class:
        qs = qs.filter(device_classification=selected_class)

    base_qs = quality_scope(RiskManagementPlan.objects.all(), request)
    total_count = base_qs.count()
    active_count = base_qs.filter(status="active").count()
    today = timezone.now().date()
    overdue_count = base_qs.filter(
        status__in=["active", "periodic_review"],
        next_review_due_date__lt=today,
    ).count()
    archived_count = base_qs.filter(status="archived").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "quality/riskmanagement/risk_management_plan/list.html",
        {
            "plans": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "active_count": active_count,
            "overdue_count": overdue_count,
            "archived_count": archived_count,
            "status_choices": RiskManagementPlan.STATUS_CHOICES,
            "device_class_choices": RiskManagementPlan.DEVICE_CLASSIFICATION_CHOICES,
            "selected_status": selected_status,
            "selected_class": selected_class,
            "q": q,
        },
    )


@login_required
def risk_management_plan_detail(request, pk):
    plan = quality_object(
        request,
        RiskManagementPlan,
        pk,
        select_related=("design_project", "lead_risk_manager", "department", "approved_signature"),
    )
    assessments = plan.assessments.select_related("design_input").order_by("-initial_rpn")
    reviews = plan.reviews.select_related("lead_reviewer", "approved_signature").order_by("-review_date")

    unacceptable_count = assessments.filter(initial_risk_level="unacceptable").count()
    alarp_count = assessments.filter(initial_risk_level="alarp").count()
    acceptable_count = assessments.filter(initial_risk_level="broadly_acceptable").count()

    from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure

    controls = RiskControlMeasure.objects.filter(
        tenant=request.tenant, risk_assessment__plan=plan
    )
    controls_count = controls.count()
    verified_controls_count = controls.filter(
        implementation_verified=True, effectiveness_verified=True
    ).count()

    stats = {
        "total_assessments": assessments.count(),
        "unacceptable_count": unacceptable_count,
        "alarp_count": alarp_count,
        "acceptable_count": acceptable_count,
        "controls_count": controls_count,
        "verified_controls_count": verified_controls_count,
    }

    return render(
        request,
        "quality/riskmanagement/risk_management_plan/detail.html",
        {
            "plan": plan,
            "assessments": assessments,
            "reviews": reviews,
            "stats": stats,
        },
    )


@login_required
def risk_management_plan_create(request):
    if request.method == "POST":
        form = RiskManagementPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.tenant = request.tenant
            plan.save()
            write_audit_log(request.user, plan, "create", tenant=request.tenant)
            messages.success(request, f"Risk Management Plan {plan.number} created successfully.")
            return redirect("quality:risk_management_plan_detail", pk=plan.pk)
    else:
        form = RiskManagementPlanForm(tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_management_plan/form.html",
        {
            "form": form,
            "plan": None,
            "is_edit": False,
        },
    )


@login_required
def risk_management_plan_edit(request, pk):
    plan = quality_object(request, RiskManagementPlan, pk)
    if request.method == "POST":
        form = RiskManagementPlanForm(request.POST, instance=plan, tenant=request.tenant)
        if form.is_valid():
            plan = form.save()
            write_audit_log(request.user, plan, "update", tenant=request.tenant)
            messages.success(request, f"Risk Management Plan {plan.number} updated successfully.")
            return redirect("quality:risk_management_plan_detail", pk=plan.pk)
    else:
        form = RiskManagementPlanForm(instance=plan, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_management_plan/form.html",
        {
            "form": form,
            "plan": plan,
            "is_edit": True,
        },
    )


@require_POST
@login_required
def risk_management_plan_delete(request, pk):
    plan = quality_object(request, RiskManagementPlan, pk)
    number = plan.number
    plan.delete()
    write_audit_log(request.user, plan, "delete", tenant=request.tenant)
    messages.success(request, f"Risk Management Plan {number} deleted successfully.")
    return redirect("quality:risk_management_plan_list")


@require_POST
@login_required
def risk_management_plan_activate(request, pk):
    plan = quality_object(request, RiskManagementPlan, pk)
    plan.status = "active"
    plan.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, plan, "activate", tenant=request.tenant)
    messages.success(request, f"Risk Management Plan {plan.number} is now Active / Effective.")
    return redirect("quality:risk_management_plan_detail", pk=plan.pk)


@require_POST
@login_required
def risk_management_plan_archive(request, pk):
    plan = quality_object(request, RiskManagementPlan, pk)
    plan.status = "archived"
    plan.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, plan, "archive", tenant=request.tenant)
    messages.info(request, f"Risk Management Plan {plan.number} has been archived.")
    return redirect("quality:risk_management_plan_detail", pk=plan.pk)


@login_required
def risk_management_plan_export(request):
    qs = quality_scope(RiskManagementPlan.objects.all(), request).select_related(
        "design_project", "lead_risk_manager", "department"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="risk_management_plans.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Title",
        "Version",
        "Status",
        "Device Classification",
        "Design Project",
        "Lead Risk Manager",
        "Department",
        "Matrix Dimension",
        "Overall Residual Risk Acceptable",
        "Next Review Due",
        "Created At",
    ])

    for p in qs:
        writer.writerow([
            csv_safe(p.number),
            csv_safe(p.title),
            csv_safe(p.plan_version),
            csv_safe(p.get_status_display()),
            csv_safe(p.get_device_classification_display()),
            csv_safe(p.design_project.number if p.design_project else ""),
            csv_safe(p.lead_risk_manager.get_full_name() or p.lead_risk_manager.username if p.lead_risk_manager else ""),
            csv_safe(p.department.name if p.department else ""),
            csv_safe(p.matrix_dimension),
            "Yes" if p.overall_residual_risk_acceptable else "No",
            csv_safe(p.next_review_due_date),
            csv_safe(p.created_at.strftime("%Y-%m-%d")),
        ])

    return response
