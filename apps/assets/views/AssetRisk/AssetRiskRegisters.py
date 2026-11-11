from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetRisk.AssetRiskRegisters import AssetRiskRegisterForm
from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_risk_register_list(request):
    qs = assets_scope(
        AssetRiskRegister.objects.select_related(
            "asset",
            "category",
            "risk_owner",
        ).defer("description"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(failure_mode__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(category__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    category_filter = request.GET.get("risk_category", "").strip()
    if category_filter:
        qs = qs.filter(risk_category=category_filter)

    level_filter = request.GET.get("inherent_risk_level", "").strip()
    if level_filter:
        qs = qs.filter(inherent_risk_level=level_filter)

    strategy_filter = request.GET.get("treatment_strategy", "").strip()
    if strategy_filter:
        qs = qs.filter(treatment_strategy=strategy_filter)

    # Aggregate KPI metrics over tenant-scoped records
    metrics = AssetRiskRegister.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        critical=Count("id", filter=Q(inherent_risk_level="critical")),
        high=Count("id", filter=Q(inherent_risk_level="high")),
        treating=Count("id", filter=Q(status="treating")),
        total_exposure=Sum("financial_exposure_amount"),
    )
    total_risks = metrics["total"] or 0
    critical_risks_count = metrics["critical"] or 0
    high_risks_count = metrics["high"] or 0
    active_treatment_count = metrics["treating"] or 0
    total_financial_exposure = metrics["total_exposure"] or Decimal("0.00")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetrisk/asset_risk_register/list.html",
        {
            "risks": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "category_choices": AssetRiskRegister.RISK_CATEGORY_CHOICES,
            "level_choices": AssetRiskRegister.RISK_LEVEL_CHOICES,
            "status_choices": AssetRiskRegister.STATUS_CHOICES,
            "strategy_choices": AssetRiskRegister.TREATMENT_STRATEGY_CHOICES,
            "total_risks": total_risks,
            "critical_risks_count": critical_risks_count,
            "high_risks_count": high_risks_count,
            "active_treatment_count": active_treatment_count,
            "total_financial_exposure": total_financial_exposure,
        },
    )


@login_required
def asset_risk_register_detail(request, pk):
    risk = assets_object(
        request,
        AssetRiskRegister,
        pk,
        select_related=["asset", "category", "risk_owner"],
    )
    mitigation_actions = risk.mitigation_actions.filter(tenant=request.tenant).select_related("assigned_to", "alternative_supplier")

    return render(
        request,
        "assets/assetrisk/asset_risk_register/detail.html",
        {
            "risk": risk,
            "mitigation_actions": mitigation_actions,
        },
    )


@login_required
@tenant_admin_required
def asset_risk_register_create(request):
    if request.method == "POST":
        form = AssetRiskRegisterForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                risk = form.save(commit=False)
                risk.tenant = request.tenant
                risk.save()
                write_audit_log(request.user, risk, "create", tenant=request.tenant)
            messages.success(request, f"Risk register entry '{risk.number}' created successfully.")
            return redirect("assets:asset_risk_register_detail", pk=risk.pk)
    else:
        form = AssetRiskRegisterForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_risk_register/form.html",
        {
            "form": form,
            "risk": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def asset_risk_register_edit(request, pk):
    risk = assets_object(request, AssetRiskRegister, pk)
    if request.method == "POST":
        form = AssetRiskRegisterForm(request.POST, instance=risk, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                risk = form.save()
                write_audit_log(request.user, risk, "update", tenant=request.tenant)
            messages.success(request, f"Risk register entry '{risk.number}' updated successfully.")
            return redirect("assets:asset_risk_register_detail", pk=risk.pk)
    else:
        form = AssetRiskRegisterForm(instance=risk, tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_risk_register/form.html",
        {
            "form": form,
            "risk": risk,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_risk_register_delete(request, pk):
    risk = assets_object(request, AssetRiskRegister, pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, risk, "delete", tenant=request.tenant)
            risk.delete()
        messages.success(request, "Risk register entry deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete risk: dependent mitigation actions exist.")
    return redirect("assets:asset_risk_register_list")


@login_required
@require_POST
def asset_risk_register_assess(request, pk):
    risk = assets_object(request, AssetRiskRegister, pk)
    if risk.status != "identified":
        messages.error(request, f"Risk '{risk.number}' cannot be marked as Assessed from status '{risk.get_status_display()}'.")
        return redirect("assets:asset_risk_register_detail", pk=risk.pk)
    with transaction.atomic():
        risk.status = "assessed"
        risk.last_reviewed_at = timezone.now()
        risk.save(update_fields=["status", "last_reviewed_at", "updated_at"])
        write_audit_log(request.user, risk, "assess", tenant=request.tenant)
    messages.success(request, f"Risk register entry '{risk.number}' marked as Assessed.")
    return redirect("assets:asset_risk_register_detail", pk=risk.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_risk_register_close(request, pk):
    risk = assets_object(request, AssetRiskRegister, pk)
    if risk.status == "closed":
        messages.warning(request, f"Risk '{risk.number}' is already closed.")
        return redirect("assets:asset_risk_register_detail", pk=risk.pk)
    with transaction.atomic():
        risk.status = "closed"
        risk.last_reviewed_at = timezone.now()
        risk.save(update_fields=["status", "last_reviewed_at", "updated_at"])
        write_audit_log(request.user, risk, "close", tenant=request.tenant)
    messages.success(request, f"Risk register entry '{risk.number}' has been Closed.")
    return redirect("assets:asset_risk_register_detail", pk=risk.pk)
