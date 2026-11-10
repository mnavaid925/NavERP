from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetWarrantyInsurance.AssetInsurancePolicies import AssetInsurancePolicyForm
from apps.assets.models import AssetCategory
from apps.assets.models.AssetWarrantyInsurance.AssetInsurancePolicies import AssetInsurancePolicy
from apps.assets.views._common import assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_insurance_policy_list(request):
    qs = assets_scope(
        AssetInsurancePolicy.objects.select_related(
            "underwriter_party",
            "broker_party",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "currency",
        ).defer("coverage_terms"),
        request,
    )

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(policy_number__icontains=q)
            | Q(title__icontains=q)
            | Q(underwriter_party__name__icontains=q)
            | Q(broker_party__name__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    policy_type_filter = request.GET.get("policy_type", "").strip()
    if policy_type_filter:
        qs = qs.filter(policy_type=policy_type_filter)

    val_basis_filter = request.GET.get("valuation_basis", "").strip()
    if val_basis_filter:
        qs = qs.filter(valuation_basis=val_basis_filter)

    cat_filter = request.GET.get("category", "").strip()
    if cat_filter and cat_filter.isdigit():
        qs = qs.filter(asset_category_id=int(cat_filter))

    # Aggregates / Stats
    tenant_base = AssetInsurancePolicy.objects.filter(tenant=request.tenant)
    today = timezone.now().date()
    forty_five_days_hence = today + timedelta(days=45)

    stats = tenant_base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        pending=Count("id", filter=Q(status="pending_renewal") | Q(status="active", expiration_date__lte=forty_five_days_hence, expiration_date__gte=today)),
        sov=Sum("total_insured_value", filter=Q(status="active")),
    )
    total_policies = stats["total"]
    active_policies = stats["active"]
    pending_renewal_count = stats["pending"]
    total_insured_value = stats["sov"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "policies": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetInsurancePolicy.STATUS_CHOICES,
        "policy_type_choices": AssetInsurancePolicy.POLICY_TYPE_CHOICES,
        "valuation_basis_choices": AssetInsurancePolicy.VALUATION_BASIS_CHOICES,
        "category_list": AssetCategory.objects.filter(tenant=request.tenant),
        "total_policies": total_policies,
        "active_policies": active_policies,
        "pending_renewal_count": pending_renewal_count,
        "total_insured_value": total_insured_value,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsurancepolicy/list.html", context)


@login_required
def asset_insurance_policy_detail(request, pk):
    policy = get_object_or_404(
        AssetInsurancePolicy.objects.select_related(
            "underwriter_party",
            "broker_party",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "currency",
            "policy_document",
            "risk_manager",
        ),
        pk=pk,
        tenant=request.tenant,
    )
    claims = policy.claims.select_related("currency", "claims_officer", "adjuster_party").order_by("-incident_date")
    context = {
        "policy": policy,
        "claims": claims,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsurancepolicy/detail.html", context)


@login_required
def asset_insurance_policy_create(request):
    if request.method == "POST":
        form = AssetInsurancePolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                policy = form.save(commit=False)
                policy.tenant = request.tenant
                if not policy.risk_manager:
                    policy.risk_manager = request.user
                policy.save()
                write_audit_log(
                    user=request.user,
                    obj=policy,
                    action="create",
                    changes={"details": f"Created insurance policy {policy.number} ({policy.policy_number}) - {policy.title}"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Insurance policy {policy.number} successfully created.")
                return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)
    else:
        form = AssetInsurancePolicyForm(tenant=request.tenant)

    context = {
        "form": form,
        "policy": None,
        "is_edit": False,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsurancepolicy/form.html", context)


@login_required
def asset_insurance_policy_edit(request, pk):
    policy = get_object_or_404(AssetInsurancePolicy, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = AssetInsurancePolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                policy = form.save()
                write_audit_log(
                    user=request.user,
                    obj=policy,
                    action="update",
                    changes={"details": f"Updated insurance policy {policy.number}"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Insurance policy {policy.number} updated.")
                return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)
    else:
        form = AssetInsurancePolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "policy": policy,
        "is_edit": True,
    }
    return render(request, "assets/assetwarrantyinsurance/assetinsurancepolicy/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_insurance_policy_delete(request, pk):
    policy = get_object_or_404(AssetInsurancePolicy, pk=pk, tenant=request.tenant)
    number = policy.number
    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=policy,
            action="delete",
            changes={"details": f"Deleted insurance policy {number}"},
            tenant=request.tenant,
        )
        policy.delete()
        messages.success(request, f"Insurance policy {number} deleted.")
    return redirect("assets:asset_insurance_policy_list")


@login_required
@require_POST
def asset_insurance_policy_activate(request, pk):
    policy = get_object_or_404(AssetInsurancePolicy, pk=pk, tenant=request.tenant)
    if policy.status != "draft":
        messages.warning(request, f"Policy {policy.number} is already {policy.get_status_display()}.")
        return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)

    with transaction.atomic():
        policy.status = "active"
        policy.save(update_fields=["status", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=policy,
            action="activate",
            changes={"details": f"Activated policy {policy.number}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Policy {policy.number} is now in force.")
    return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)


@login_required
@require_POST
def asset_insurance_policy_renew(request, pk):
    policy = get_object_or_404(AssetInsurancePolicy, pk=pk, tenant=request.tenant)
    if policy.status not in ["active", "pending_renewal", "expired"]:
        messages.warning(request, f"Policy {policy.number} cannot be renewed in its current state ({policy.get_status_display()}).")
        return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)
    with transaction.atomic():
        base_date = max(policy.expiration_date, timezone.now().date())
        policy.expiration_date = base_date + timedelta(days=365)
        policy.status = "active"
        policy.save(update_fields=["expiration_date", "status", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=policy,
            action="renew",
            changes={"details": f"Renewed policy {policy.number} through {policy.expiration_date}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Policy {policy.number} renewed through {policy.expiration_date}.")
    return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_insurance_policy_cancel(request, pk):
    policy = get_object_or_404(AssetInsurancePolicy, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        policy.status = "cancelled"
        policy.save(update_fields=["status", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=policy,
            action="cancel",
            changes={"details": f"Cancelled policy {policy.number}"},
            tenant=request.tenant,
        )
        messages.info(request, f"Policy {policy.number} has been cancelled.")
    return redirect("assets:asset_insurance_policy_detail", pk=policy.pk)
