import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.RiskManagement.RiskManagementPlans import RiskManagementPlanForm
from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
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
    today = timezone.now().date()
    counts = base_qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        overdue_count=Count("id", filter=Q(
            status__in=["active", "periodic_review"],
            next_review_due_date__lt=today,
        )),
        archived_count=Count("id", filter=Q(status="archived")),
    )
    total_count = counts["total_count"] or 0
    active_count = counts["active_count"] or 0
    overdue_count = counts["overdue_count"] or 0
    archived_count = counts["archived_count"] or 0

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

    assessment_stats = assessments.aggregate(
        total=Count("id"),
        unacceptable=Count("id", filter=Q(initial_risk_level="unacceptable")),
        alarp=Count("id", filter=Q(initial_risk_level="alarp")),
        acceptable=Count("id", filter=Q(initial_risk_level="broadly_acceptable")),
    )

    control_stats = RiskControlMeasure.objects.filter(
        tenant=request.tenant, risk_assessment__plan=plan
    ).aggregate(
        total=Count("id"),
        verified=Count("id", filter=Q(implementation_verified=True, effectiveness_verified=True)),
    )

    stats = {
        "total_assessments": assessment_stats["total"] or 0,
        "unacceptable_count": assessment_stats["unacceptable"] or 0,
        "alarp_count": assessment_stats["alarp"] or 0,
        "acceptable_count": assessment_stats["acceptable"] or 0,
        "controls_count": control_stats["total"] or 0,
        "verified_controls_count": control_stats["verified"] or 0,
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
    if plan.approved_signature_id or plan.status in ("active", "archived"):
        messages.error(
            request,
            f"Risk Management Plan {plan.number} cannot be modified while {plan.get_status_display().lower()} or electronically signed. Create a new revision.",
        )
        return redirect("quality:risk_management_plan_detail", pk=plan.pk)

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
@tenant_admin_required
def risk_management_plan_delete(request, pk):
    plan = quality_object(request, RiskManagementPlan, pk)
    number = plan.number
    write_audit_log(request.user, plan, "delete", tenant=request.tenant)
    plan.delete()
    messages.success(request, f"Risk Management Plan {number} deleted successfully.")
    return redirect("quality:risk_management_plan_list")


@require_POST
@login_required
@tenant_admin_required
def risk_management_plan_activate(request, pk):
    plan = quality_object(request, RiskManagementPlan, pk)
    plan.status = "active"
    plan.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, plan, "activate", tenant=request.tenant)
    messages.success(request, f"Risk Management Plan {plan.number} is now Active / Effective.")
    return redirect("quality:risk_management_plan_detail", pk=plan.pk)


@require_POST
@login_required
@tenant_admin_required
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
