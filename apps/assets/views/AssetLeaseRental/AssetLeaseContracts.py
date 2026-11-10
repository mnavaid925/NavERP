from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContractForm
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log


@login_required
def asset_lease_contract_list(request):
    qs = assets_scope(
        AssetLeaseContract.objects.select_related(
            "lessor",
            "asset",
            "category",
            "fixed_asset",
            "approved_by",
        ).defer("notes", "classification_notes"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(master_lease_agreement_ref__icontains=q)
            | Q(lessor__name__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(fixed_asset__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    classification_filter = request.GET.get("classification", "").strip()
    if classification_filter:
        qs = qs.filter(classification=classification_filter)

    lessor_filter = request.GET.get("lessor", "").strip()
    if lessor_filter and lessor_filter.isdigit():
        qs = qs.filter(lessor_id=int(lessor_filter))

    # KPI aggregation
    base_tenant_qs = assets_scope(AssetLeaseContract.objects.all(), request)
    kpi_agg = base_tenant_qs.aggregate(
        total_leases=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        total_liability=Sum("current_lease_liability"),
        total_rou_value=Sum("current_rou_asset_carrying_value"),
    )
    total_leases = kpi_agg["total_leases"] or 0
    active_count = kpi_agg["active_count"] or 0
    total_liability = kpi_agg["total_liability"] or Decimal("0.00")
    total_rou_value = kpi_agg["total_rou_value"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    lessor_list = Party.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")

    context = {
        "leases": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetLeaseContract.STATUS_CHOICES,
        "classification_choices": AssetLeaseContract.CLASSIFICATION_CHOICES,
        "lessor_list": lessor_list,
        "total_leases": total_leases,
        "active_count": active_count,
        "total_liability": total_liability,
        "total_rou_value": total_rou_value,
        "q": q,
        "status": status_filter,
        "classification": classification_filter,
        "lessor": lessor_filter,
    }
    return render(request, "assets/assetleaserental/asset_lease_contract/list.html", context)


@login_required
def asset_lease_contract_detail(request, pk):
    lease = assets_object(
        request,
        AssetLeaseContract,
        pk,
        select_related=["lessor", "asset", "category", "fixed_asset", "approved_by"],
    )
    schedules = lease.payment_schedules.all().order_by("period_number")
    modifications = lease.modifications.all().order_by("-effective_date")

    context = {
        "lease": lease,
        "schedules": schedules,
        "modifications": modifications,
    }
    return render(request, "assets/assetleaserental/asset_lease_contract/detail.html", context)


@login_required
def asset_lease_contract_create(request):
    if request.method == "POST":
        form = AssetLeaseContractForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.calculate_present_value()
                instance.evaluate_statutory_classification()
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "create",
                    changes=f"Created lease contract {instance.number} ({instance.title})",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease contract {instance.number} created successfully.")
                return redirect("assets:asset_lease_contract_detail", pk=instance.pk)
    else:
        form = AssetLeaseContractForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_contract/form.html",
        {"form": form, "title": "New Lease Contract", "is_edit": False},
    )


@login_required
def asset_lease_contract_edit(request, pk):
    lease = assets_object(request, AssetLeaseContract, pk)

    if request.method == "POST":
        form = AssetLeaseContractForm(request.POST, instance=lease, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.calculate_present_value()
                instance.evaluate_statutory_classification()
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "update",
                    changes=f"Updated lease contract {instance.number}",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease contract {instance.number} updated successfully.")
                return redirect("assets:asset_lease_contract_detail", pk=instance.pk)
    else:
        form = AssetLeaseContractForm(instance=lease, tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_contract/form.html",
        {"form": form, "title": f"Edit Lease Contract — {lease.number}", "is_edit": True, "lease": lease},
    )


@require_POST
@tenant_admin_required
def asset_lease_contract_delete(request, pk):
    lease = assets_object(request, AssetLeaseContract, pk)
    num = lease.number
    write_audit_log(
        request.user,
        lease,
        "delete",
        changes=f"Deleted lease contract {num}",
        tenant=request.tenant,
    )
    lease.delete()
    messages.success(request, f"Lease contract {num} was deleted.")
    return redirect("assets:asset_lease_contract_list")


@require_POST
@login_required
def asset_lease_contract_calculate(request, pk):
    lease = assets_object(request, AssetLeaseContract, pk)
    pv_liability, initial_rou = lease.calculate_present_value()
    classification = lease.evaluate_statutory_classification()
    lease.save()

    write_audit_log(
        request.user,
        lease,
        "calculate",
        changes=(
            f"Calculated present value for contract {lease.number}: "
            f"PV Liability=${pv_liability:,.2f}, Initial ROU=${initial_rou:,.2f}, "
            f"Classification={lease.get_classification_display()}"
        ),
        tenant=request.tenant,
    )

    messages.info(
        request,
        f"Contract calculated: Liability PV=${pv_liability:,.2f}, ROU Asset=${initial_rou:,.2f}, "
        f"Statutory Classification: {lease.get_classification_display()}.",
    )
    return redirect("assets:asset_lease_contract_detail", pk=lease.pk)


@require_POST
@tenant_admin_required
def asset_lease_contract_activate(request, pk):
    lease = assets_object(request, AssetLeaseContract, pk)
    if lease.status not in ["draft", "pending_approval"]:
        messages.warning(request, f"Contract {lease.number} is already {lease.get_status_display()}.")
        return redirect("assets:asset_lease_contract_detail", pk=lease.pk)

    with transaction.atomic():
        lease.calculate_present_value()
        lease.evaluate_statutory_classification()
        lease.status = "active"
        lease.approved_by = request.user
        lease.save()

        count = lease.generate_amortization_schedule()

        write_audit_log(
            request.user,
            lease,
            "activate",
            changes=f"Activated lease contract {lease.number} and generated {count} payment schedule rows",
            tenant=request.tenant,
        )

        messages.success(
            request,
            f"Lease contract {lease.number} activated! {count} payment amortization periods generated.",
        )
    return redirect("assets:asset_lease_contract_detail", pk=lease.pk)


@require_POST
@login_required
def asset_lease_contract_terminate(request, pk):
    lease = assets_object(request, AssetLeaseContract, pk)
    action_type = request.POST.get("action_type", "terminated")
    if action_type == "buyout":
        lease.status = "buyout"
        msg = f"Lease contract {lease.number} marked as Asset Buyout / Purchased."
    else:
        lease.status = "terminated"
        msg = f"Lease contract {lease.number} early terminated."

    with transaction.atomic():
        lease.save()
        lease.payment_schedules.filter(status="scheduled").update(status="cancelled")
        write_audit_log(
            request.user,
            lease,
            "terminate",
            changes=msg,
            tenant=request.tenant,
        )
    messages.success(request, msg)
    return redirect("assets:asset_lease_contract_detail", pk=lease.pk)
