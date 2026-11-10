from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModificationForm
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModification
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_lease_modification_list(request):
    qs = assets_scope(
        AssetLeaseModification.objects.select_related(
            "lease_contract",
            "lease_contract__lessor",
            "requested_by",
            "approved_by",
        ).defer("notes", "justification"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(justification__icontains=q)
            | Q(lease_contract__number__icontains=q)
            | Q(lease_contract__title__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("type", "").strip()
    if type_filter:
        qs = qs.filter(modification_type=type_filter)

    lease_filter = request.GET.get("lease", "").strip()
    if lease_filter and lease_filter.isdigit():
        qs = qs.filter(lease_contract_id=int(lease_filter))

    base_tenant_qs = assets_scope(AssetLeaseModification.objects.all(), request)
    kpi_agg = base_tenant_qs.aggregate(
        total_modifications=Count("id"),
        executed_count=Count("id", filter=Q(status="executed")),
        total_adjustments=Sum("liability_adjustment"),
    )
    total_modifications = kpi_agg["total_modifications"] or 0
    executed_count = kpi_agg["executed_count"] or 0
    total_adjustments = kpi_agg["total_adjustments"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    lease_list = AssetLeaseContract.objects.filter(tenant=request.tenant).only("id", "number", "title").order_by("-id")

    context = {
        "modifications": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetLeaseModification.STATUS_CHOICES,
        "type_choices": AssetLeaseModification.MODIFICATION_TYPE_CHOICES,
        "lease_list": lease_list,
        "total_modifications": total_modifications,
        "executed_count": executed_count,
        "total_adjustments": total_adjustments,
        "q": q,
        "status": status_filter,
        "type": type_filter,
        "lease": lease_filter,
    }
    return render(request, "assets/assetleaserental/asset_lease_modification/list.html", context)


@login_required
def asset_lease_modification_detail(request, pk):
    modification = assets_object(
        request,
        AssetLeaseModification,
        pk,
        select_related=["lease_contract", "lease_contract__lessor", "requested_by", "approved_by"],
    )
    return render(
        request,
        "assets/assetleaserental/asset_lease_modification/detail.html",
        {"modification": modification},
    )


@login_required
def asset_lease_modification_create(request):
    initial = {}
    lease_param = request.GET.get("lease")
    if lease_param and lease_param.isdigit():
        lease = assets_object(request, AssetLeaseContract, int(lease_param))
        initial["lease_contract"] = lease.pk
        initial["prior_lease_liability"] = lease.current_lease_liability
        initial["prior_rou_asset_value"] = lease.current_rou_asset_carrying_value
        initial["revised_term_months"] = lease.lease_term_months
        initial["revised_payment_amount"] = lease.payment_amount
        initial["revised_discount_rate_pct"] = lease.discount_rate_pct

    if request.method == "POST":
        form = AssetLeaseModificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.liability_adjustment = (
                    instance.revised_lease_liability - instance.prior_lease_liability
                )
                instance.rou_asset_adjustment = (
                    instance.revised_rou_asset_value - instance.prior_rou_asset_value
                )
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "create",
                    changes=f"Created lease modification {instance.number} ({instance.get_modification_type_display()})",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease modification {instance.number} created.")
                return redirect("assets:asset_lease_modification_detail", pk=instance.pk)
    else:
        form = AssetLeaseModificationForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_modification/form.html",
        {"form": form, "title": "New Lease Modification", "is_edit": False},
    )


@login_required
def asset_lease_modification_edit(request, pk):
    modification = assets_object(request, AssetLeaseModification, pk)

    if request.method == "POST":
        form = AssetLeaseModificationForm(request.POST, instance=modification, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.liability_adjustment = (
                    instance.revised_lease_liability - instance.prior_lease_liability
                )
                instance.rou_asset_adjustment = (
                    instance.revised_rou_asset_value - instance.prior_rou_asset_value
                )
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "update",
                    changes=f"Updated lease modification {instance.number}",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease modification {instance.number} updated.")
                return redirect("assets:asset_lease_modification_detail", pk=instance.pk)
    else:
        form = AssetLeaseModificationForm(instance=modification, tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_modification/form.html",
        {"form": form, "title": f"Edit Modification — {modification.number}", "is_edit": True, "modification": modification},
    )


@require_POST
@tenant_admin_required
def asset_lease_modification_delete(request, pk):
    modification = assets_object(request, AssetLeaseModification, pk)
    num = modification.number
    contract_pk = modification.lease_contract_id
    if modification.status == "executed":
        messages.warning(request, f"Cannot delete modification {num} because it has already been executed.")
        return redirect("assets:asset_lease_contract_detail", pk=contract_pk)

    write_audit_log(
        request.user,
        modification,
        "delete",
        changes=f"Deleted lease modification {num}",
        tenant=request.tenant,
    )
    modification.delete()
    messages.success(request, f"Modification {num} deleted.")
    return redirect("assets:asset_lease_contract_detail", pk=contract_pk)


@require_POST
@tenant_admin_required
def asset_lease_modification_approve(request, pk):
    modification = assets_object(
        request,
        AssetLeaseModification,
        pk,
        select_related=["lease_contract"],
    )
    if modification.status == "executed":
        messages.warning(request, f"Modification {modification.number} is already executed.")
        return redirect("assets:asset_lease_modification_detail", pk=modification.pk)

    with transaction.atomic():
        contract = modification.lease_contract
        modification.liability_adjustment = (
            modification.revised_lease_liability - modification.prior_lease_liability
        )
        modification.rou_asset_adjustment = (
            modification.revised_rou_asset_value - modification.prior_rou_asset_value
        )
        modification.approved_by = request.user
        modification.status = "executed"
        modification.save()

        # Update contract balances and terms
        contract.current_lease_liability = modification.revised_lease_liability
        contract.current_rou_asset_carrying_value = modification.revised_rou_asset_value

        if modification.modification_type == "full_termination":
            contract.status = "terminated"
            contract.payment_schedules.filter(status="scheduled").update(status="cancelled")
        else:
            contract.status = "modified"

        if modification.revised_term_months:
            contract.lease_term_months = modification.revised_term_months
        if modification.revised_payment_amount:
            contract.payment_amount = modification.revised_payment_amount
        if modification.revised_discount_rate_pct:
            contract.discount_rate_pct = modification.revised_discount_rate_pct

        contract.save()

        write_audit_log(
            request.user,
            modification,
            "execute",
            changes=f"Approved and executed lease modification {modification.number} on contract {contract.number}",
            tenant=request.tenant,
        )

        messages.success(
            request,
            f"Modification {modification.number} approved! Contract {contract.number} balances and terms remeasured.",
        )
    return redirect("assets:asset_lease_modification_detail", pk=modification.pk)
