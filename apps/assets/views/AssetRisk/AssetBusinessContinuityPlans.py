from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, ProtectedError, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetRisk.AssetBusinessContinuityPlans import AssetBusinessContinuityPlanForm
from apps.assets.models.AssetRisk.AssetBusinessContinuityPlans import AssetBusinessContinuityPlan
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_business_continuity_plan_list(request):
    qs = assets_scope(
        AssetBusinessContinuityPlan.objects.select_related(
            "primary_asset",
            "backup_redundant_asset",
            "emergency_lead",
        ).defer("failover_procedure", "failback_procedure"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(primary_asset__name__icontains=q)
            | Q(backup_redundant_asset__name__icontains=q)
            | Q(alternate_facility_site__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    redundancy_filter = request.GET.get("redundancy_type", "").strip()
    if redundancy_filter:
        qs = qs.filter(redundancy_type=redundancy_filter)

    scenario_filter = request.GET.get("disaster_scenario", "").strip()
    if scenario_filter:
        qs = qs.filter(disaster_scenario=scenario_filter)

    # Aggregate KPI metrics over tenant-scoped records
    metrics = AssetBusinessContinuityPlan.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        spof=Count("id", filter=Q(redundancy_type="none_single_point_of_failure")),
        avg_rto=Avg("recovery_time_objective_hours"),
    )
    total_plans = metrics["total"] or 0
    active_plans_count = metrics["active"] or 0
    spof_count = metrics["spof"] or 0
    avg_rto_hours = round(metrics["avg_rto"] or 0.0, 1)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetrisk/asset_business_continuity/list.html",
        {
            "plans": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "redundancy_choices": AssetBusinessContinuityPlan.REDUNDANCY_TYPE_CHOICES,
            "scenario_choices": AssetBusinessContinuityPlan.DISASTER_SCENARIO_CHOICES,
            "status_choices": AssetBusinessContinuityPlan.STATUS_CHOICES,
            "total_plans": total_plans,
            "active_plans_count": active_plans_count,
            "spof_count": spof_count,
            "avg_rto_hours": avg_rto_hours,
        },
    )


@login_required
def asset_business_continuity_plan_detail(request, pk):
    plan = assets_object(
        AssetBusinessContinuityPlan.objects.select_related(
            "primary_asset",
            "backup_redundant_asset",
            "emergency_lead",
        ),
        pk,
        request,
    )

    return render(
        request,
        "assets/assetrisk/asset_business_continuity/detail.html",
        {
            "plan": plan,
        },
    )


@login_required
@tenant_admin_required
def asset_business_continuity_plan_create(request):
    if request.method == "POST":
        form = AssetBusinessContinuityPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                plan = form.save(commit=False)
                plan.tenant = request.tenant
                plan.save()
                write_audit_log(request.user, plan, "create", tenant=request.tenant)
            messages.success(request, f"Business continuity plan '{plan.number}' created successfully.")
            return redirect("assets:asset_business_continuity_plan_detail", pk=plan.pk)
    else:
        form = AssetBusinessContinuityPlanForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_business_continuity/form.html",
        {
            "form": form,
            "plan": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def asset_business_continuity_plan_edit(request, pk):
    plan = assets_object(AssetBusinessContinuityPlan, pk, request)
    if request.method == "POST":
        form = AssetBusinessContinuityPlanForm(request.POST, instance=plan, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                plan = form.save()
                write_audit_log(request.user, plan, "update", tenant=request.tenant)
            messages.success(request, f"Business continuity plan '{plan.number}' updated successfully.")
            return redirect("assets:asset_business_continuity_plan_detail", pk=plan.pk)
    else:
        form = AssetBusinessContinuityPlanForm(instance=plan, tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_business_continuity/form.html",
        {
            "form": form,
            "plan": plan,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_business_continuity_plan_delete(request, pk):
    plan = assets_object(AssetBusinessContinuityPlan, pk, request)
    try:
        with transaction.atomic():
            write_audit_log(request.user, plan, "delete", tenant=request.tenant)
            plan.delete()
        messages.success(request, "Business continuity plan deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete plan: dependent resources exist.")
    return redirect("assets:asset_business_continuity_plan_list")


@login_required
@require_POST
def asset_business_continuity_plan_activate(request, pk):
    plan = assets_object(AssetBusinessContinuityPlan, pk, request)
    with transaction.atomic():
        plan.status = "active"
        plan.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, plan, "activate", tenant=request.tenant)
    messages.success(request, f"Business continuity plan '{plan.number}' activated.")
    return redirect("assets:asset_business_continuity_plan_detail", pk=plan.pk)


@login_required
@require_POST
def asset_business_continuity_plan_drill(request, pk):
    plan = assets_object(AssetBusinessContinuityPlan, pk, request)
    drill_result = request.POST.get("drill_result", "passed").strip()
    if drill_result not in dict(AssetBusinessContinuityPlan.DRILL_RESULT_CHOICES):
        drill_result = "passed"
    with transaction.atomic():
        plan.last_drill_date = timezone.now().date()
        plan.drill_result = drill_result
        plan.save(update_fields=["last_drill_date", "drill_result", "updated_at"])
        write_audit_log(request.user, plan, "record_drill", changes={"drill_result": drill_result}, tenant=request.tenant)
    messages.success(request, f"Disaster simulation drill recorded for '{plan.number}' with result '{drill_result}'.")
    return redirect("assets:asset_business_continuity_plan_detail", pk=plan.pk)
