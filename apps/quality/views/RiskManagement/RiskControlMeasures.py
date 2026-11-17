import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.RiskManagement.RiskControlMeasures import RiskControlMeasureForm
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
def risk_control_measure_list(request):
    qs = quality_scope(RiskControlMeasure.objects.all(), request).select_related(
        "risk_assessment", "risk_assessment__plan", "assigned_to", "design_input", "controlled_document", "design_verification"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
        )

    selected_hierarchy = request.GET.get("control_hierarchy", "").strip()
    if selected_hierarchy:
        qs = qs.filter(control_hierarchy=selected_hierarchy)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_plan = request.GET.get("plan", "").strip()
    if selected_plan and selected_plan.isdigit():
        qs = qs.filter(risk_assessment__plan_id=int(selected_plan))

    base_qs = quality_scope(RiskControlMeasure.objects.all(), request)
    counts = base_qs.aggregate(
        total_count=Count("id"),
        verified_count=Count("id", filter=Q(implementation_verified=True, effectiveness_verified=True)),
        inherent_safety_count=Count("id", filter=Q(control_hierarchy="inherent_safety")),
        in_progress_count=Count("id", filter=Q(status="in_progress")),
    )
    total_count = counts["total_count"] or 0
    verified_count = counts["verified_count"] or 0
    inherent_safety_count = counts["inherent_safety_count"] or 0
    in_progress_count = counts["in_progress_count"] or 0

    plans = quality_scope(RiskManagementPlan.objects.all(), request).only("id", "number", "title").order_by("number")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "quality/riskmanagement/risk_control_measure/list.html",
        {
            "control_measures": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "verified_count": verified_count,
            "inherent_safety_count": inherent_safety_count,
            "in_progress_count": in_progress_count,
            "hierarchy_choices": RiskControlMeasure.CONTROL_HIERARCHY_CHOICES,
            "status_choices": RiskControlMeasure.STATUS_CHOICES,
            "plans": plans,
            "selected_hierarchy": selected_hierarchy,
            "selected_status": selected_status,
            "selected_plan": selected_plan,
            "q": q,
        },
    )


@login_required
def risk_control_measure_detail(request, pk):
    control_measure = quality_object(
        request,
        RiskControlMeasure,
        pk,
        select_related=(
            "risk_assessment",
            "risk_assessment__plan",
            "assigned_to",
            "design_input",
            "controlled_document",
            "design_verification",
        ),
    )

    return render(
        request,
        "quality/riskmanagement/risk_control_measure/detail.html",
        {
            "control_measure": control_measure,
        },
    )


@login_required
def risk_control_measure_create(request):
    initial = {}
    assessment_param = request.GET.get("assessment", "").strip()
    if assessment_param and assessment_param.isdigit():
        initial["risk_assessment"] = int(assessment_param)

    if request.method == "POST":
        form = RiskControlMeasureForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            measure = form.save(commit=False)
            measure.tenant = request.tenant
            measure.save()
            write_audit_log(request.user, measure, "create", tenant=request.tenant)
            messages.success(request, f"Risk Control Measure {measure.number} created successfully.")
            return redirect("quality:risk_control_measure_detail", pk=measure.pk)
    else:
        form = RiskControlMeasureForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_control_measure/form.html",
        {
            "form": form,
            "control_measure": None,
            "is_edit": False,
        },
    )


@login_required
def risk_control_measure_edit(request, pk):
    control_measure = quality_object(request, RiskControlMeasure, pk)
    if request.method == "POST":
        form = RiskControlMeasureForm(request.POST, instance=control_measure, tenant=request.tenant)
        if form.is_valid():
            control_measure = form.save()
            write_audit_log(request.user, control_measure, "update", tenant=request.tenant)
            messages.success(request, f"Risk Control Measure {control_measure.number} updated successfully.")
            return redirect("quality:risk_control_measure_detail", pk=control_measure.pk)
    else:
        form = RiskControlMeasureForm(instance=control_measure, tenant=request.tenant)

    return render(
        request,
        "quality/riskmanagement/risk_control_measure/form.html",
        {
            "form": form,
            "control_measure": control_measure,
            "is_edit": True,
        },
    )


@require_POST
@login_required
@tenant_admin_required
def risk_control_measure_delete(request, pk):
    control_measure = quality_object(request, RiskControlMeasure, pk)
    number = control_measure.number
    assessment_id = control_measure.risk_assessment_id
    write_audit_log(request.user, control_measure, "delete", tenant=request.tenant)
    control_measure.delete()
    messages.success(request, f"Risk Control Measure {number} deleted successfully.")
    return redirect("quality:risk_assessment_detail", pk=assessment_id)


@require_POST
@login_required
def risk_control_measure_verify_impl(request, pk):
    control_measure = quality_object(request, RiskControlMeasure, pk)
    control_measure.implementation_verified = True
    if control_measure.effectiveness_verified:
        control_measure.status = "verified"
    elif control_measure.status == "planned":
        control_measure.status = "implemented"
    control_measure.save(update_fields=["implementation_verified", "status", "updated_at"])
    write_audit_log(request.user, control_measure, "verify", tenant=request.tenant)
    messages.success(request, f"Implementation verified for {control_measure.number}.")
    return redirect("quality:risk_control_measure_detail", pk=control_measure.pk)


@require_POST
@login_required
def risk_control_measure_verify_eff(request, pk):
    control_measure = quality_object(request, RiskControlMeasure, pk)
    control_measure.effectiveness_verified = True
    if control_measure.implementation_verified:
        control_measure.status = "verified"
    control_measure.save(update_fields=["effectiveness_verified", "status", "updated_at"])
    write_audit_log(request.user, control_measure, "verify", tenant=request.tenant)
    messages.success(request, f"Effectiveness verified for {control_measure.number}.")
    return redirect("quality:risk_control_measure_detail", pk=control_measure.pk)


@login_required
def risk_control_measure_export(request):
    qs = quality_scope(RiskControlMeasure.objects.all(), request).select_related(
        "risk_assessment", "risk_assessment__plan", "assigned_to", "design_input", "controlled_document", "design_verification"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="risk_control_measures.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Risk Item",
        "Hierarchy Tier",
        "Title",
        "Assigned To",
        "Status",
        "Design Input",
        "Controlled Document",
        "Design Verification",
        "Implementation Verified",
        "Effectiveness Verified",
        "Introduces New Hazard",
        "Created At",
    ])

    for c in qs:
        writer.writerow([
            csv_safe(c.number),
            csv_safe(c.risk_assessment.number if c.risk_assessment else ""),
            csv_safe(c.get_control_hierarchy_display()),
            csv_safe(c.title),
            csv_safe(c.assigned_to.get_full_name() or c.assigned_to.username if c.assigned_to else ""),
            csv_safe(c.get_status_display()),
            csv_safe(c.design_input.identifier if c.design_input else ""),
            csv_safe(c.controlled_document.number if c.controlled_document else ""),
            csv_safe(c.design_verification.number if c.design_verification else ""),
            "Yes" if c.implementation_verified else "No",
            "Yes" if c.effectiveness_verified else "No",
            "Yes" if c.introduces_new_hazard else "No",
            csv_safe(c.created_at.strftime("%Y-%m-%d")),
        ])

    return response
