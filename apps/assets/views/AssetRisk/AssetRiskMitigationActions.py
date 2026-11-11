from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetRisk.AssetRiskMitigationActions import AssetRiskMitigationActionForm
from apps.assets.models.AssetRisk.AssetRiskMitigationActions import AssetRiskMitigationAction
from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_risk_mitigation_action_list(request):
    qs = assets_scope(
        AssetRiskMitigationAction.objects.select_related(
            "risk",
            "assigned_to",
            "alternative_supplier",
        ).defer("description", "verification_notes"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(risk__number__icontains=q)
            | Q(risk__title__icontains=q)
            | Q(assigned_to__username__icontains=q)
            | Q(assigned_to__first_name__icontains=q)
            | Q(assigned_to__last_name__icontains=q)
            | Q(alternative_supplier__name__icontains=q)
        )

    type_filter = request.GET.get("action_type", "").strip()
    if type_filter:
        qs = qs.filter(action_type=type_filter)

    priority_filter = request.GET.get("priority", "").strip()
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    effectiveness_filter = request.GET.get("effectiveness_rating", "").strip()
    if effectiveness_filter:
        qs = qs.filter(effectiveness_rating=effectiveness_filter)

    # Aggregate KPI metrics over tenant-scoped records
    metrics = AssetRiskMitigationAction.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        in_progress=Count("id", filter=Q(status="in_progress")),
        verified=Count("id", filter=Q(status="verified_effective")),
        total_estimated=Sum("estimated_cost"),
        total_actual=Sum("actual_cost"),
    )
    total_actions = metrics["total"] or 0
    in_progress_count = metrics["in_progress"] or 0
    verified_count = metrics["verified"] or 0
    total_estimated_cost = metrics["total_estimated"] or Decimal("0.00")
    total_actual_cost = metrics["total_actual"] or Decimal("0.00")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetrisk/asset_risk_mitigation/list.html",
        {
            "actions": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "type_choices": AssetRiskMitigationAction.ACTION_TYPE_CHOICES,
            "priority_choices": AssetRiskMitigationAction.PRIORITY_CHOICES,
            "status_choices": AssetRiskMitigationAction.STATUS_CHOICES,
            "effectiveness_choices": AssetRiskMitigationAction.EFFECTIVENESS_CHOICES,
            "total_actions": total_actions,
            "in_progress_count": in_progress_count,
            "verified_count": verified_count,
            "total_estimated_cost": total_estimated_cost,
            "total_actual_cost": total_actual_cost,
        },
    )


@login_required
def asset_risk_mitigation_action_detail(request, pk):
    action = assets_object(
        request,
        AssetRiskMitigationAction,
        pk,
        select_related=[
            "risk",
            "assigned_to",
            "alternative_supplier",
        ],
    )

    return render(
        request,
        "assets/assetrisk/asset_risk_mitigation/detail.html",
        {
            "action": action,
        },
    )


@login_required
@tenant_admin_required
def asset_risk_mitigation_action_create(request):
    initial = {}
    risk_pk = request.GET.get("risk", "").strip()
    if risk_pk and risk_pk.isdigit():
        risk_obj = AssetRiskRegister.objects.filter(tenant=request.tenant, pk=int(risk_pk)).first()
        if risk_obj:
            initial["risk"] = risk_obj

    if request.method == "POST":
        form = AssetRiskMitigationActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                action = form.save(commit=False)
                action.tenant = request.tenant
                action.save()
                write_audit_log(request.user, action, "create", tenant=request.tenant)
            messages.success(request, f"Mitigation action '{action.number}' created successfully.")
            return redirect("assets:asset_risk_mitigation_action_detail", pk=action.pk)
    else:
        form = AssetRiskMitigationActionForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_risk_mitigation/form.html",
        {
            "form": form,
            "action": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def asset_risk_mitigation_action_edit(request, pk):
    action = assets_object(request, AssetRiskMitigationAction, pk)
    if request.method == "POST":
        form = AssetRiskMitigationActionForm(request.POST, instance=action, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                action = form.save()
                write_audit_log(request.user, action, "update", tenant=request.tenant)
            messages.success(request, f"Mitigation action '{action.number}' updated successfully.")
            return redirect("assets:asset_risk_mitigation_action_detail", pk=action.pk)
    else:
        form = AssetRiskMitigationActionForm(instance=action, tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_risk_mitigation/form.html",
        {
            "form": form,
            "action": action,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_risk_mitigation_action_delete(request, pk):
    action = assets_object(request, AssetRiskMitigationAction, pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, action, "delete", tenant=request.tenant)
            action.delete()
        messages.success(request, "Mitigation action deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete action: dependent records exist.")
    return redirect("assets:asset_risk_mitigation_action_list")


@login_required
@require_POST
def asset_risk_mitigation_action_complete(request, pk):
    action = assets_object(request, AssetRiskMitigationAction, pk)
    if action.status not in ["planned", "in_progress"]:
        messages.warning(request, f"Mitigation action '{action.number}' cannot be marked Completed from status '{action.get_status_display()}'.")
        return redirect("assets:asset_risk_mitigation_action_detail", pk=action.pk)
    with transaction.atomic():
        action.status = "completed"
        action.actual_completion_date = timezone.now().date()
        action.save(update_fields=["status", "actual_completion_date", "updated_at"])
        write_audit_log(request.user, action, "complete", tenant=request.tenant)
    messages.success(request, f"Mitigation action '{action.number}' marked as Completed.")
    return redirect("assets:asset_risk_mitigation_action_detail", pk=action.pk)


@login_required
@require_POST
def asset_risk_mitigation_action_verify(request, pk):
    action = assets_object(request, AssetRiskMitigationAction, pk)
    if action.status != "completed":
        messages.warning(request, f"Mitigation action '{action.number}' cannot be verified from status '{action.get_status_display()}'.")
        return redirect("assets:asset_risk_mitigation_action_detail", pk=action.pk)
    effectiveness = request.POST.get("effectiveness_rating", "highly_effective").strip()
    if effectiveness not in dict(AssetRiskMitigationAction.EFFECTIVENESS_CHOICES):
        effectiveness = "highly_effective"
    with transaction.atomic():
        action.status = "verified_effective"
        action.effectiveness_rating = effectiveness
        action.save(update_fields=["status", "effectiveness_rating", "updated_at"])
        write_audit_log(request.user, action, "verify", changes={"effectiveness_rating": effectiveness}, tenant=request.tenant)
    messages.success(request, f"Mitigation action '{action.number}' verified as '{effectiveness}'.")
    return redirect("assets:asset_risk_mitigation_action_detail", pk=action.pk)
