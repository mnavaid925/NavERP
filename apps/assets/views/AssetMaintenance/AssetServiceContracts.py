from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetMaintenance.AssetServiceContracts import (
    AssetServiceContractForm,
    AssetServiceContractRenewForm,
)
from apps.assets.models.AssetMaintenance.AssetServiceContracts import AssetServiceContract
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_service_contract_list(request):
    qs = AssetServiceContract.objects.filter(tenant=request.tenant).select_related(
        "vendor", "fixed_asset", "operational_asset", "currency"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(contract_number__icontains=q)
            | Q(title__icontains=q)
            | Q(vendor__name__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_type = request.GET.get("contract_type", "").strip()
    if selected_type:
        qs = qs.filter(contract_type=selected_type)

    selected_billing = request.GET.get("billing_frequency", "").strip()
    if selected_billing:
        qs = qs.filter(billing_frequency=selected_billing)

    today = timezone.now().date()
    expiring_threshold = today + timedelta(days=30)
    all_tenant_contracts = AssetServiceContract.objects.filter(tenant=request.tenant)
    agg = all_tenant_contracts.aggregate(
        total_contracts=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        expiring_soon_count=Count(
            "id",
            filter=Q(status="active", end_date__gte=today, end_date__lte=expiring_threshold),
        ),
        total_contract_value=Sum("contract_value", filter=Q(status="active")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "service_contracts": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": q,
        "status_choices": AssetServiceContract.STATUS_CHOICES,
        "contract_type_choices": AssetServiceContract.CONTRACT_TYPE_CHOICES,
        "billing_frequency_choices": AssetServiceContract.BILLING_FREQUENCY_CHOICES,
        "total_contracts": agg["total_contracts"] or 0,
        "active_count": agg["active_count"] or 0,
        "expiring_soon_count": agg["expiring_soon_count"] or 0,
        "total_contract_value": agg["total_contract_value"] or Decimal("0.00"),
    }
    return render(request, "assets/asset_maintenance/asset_service_contract/list.html", context)


@login_required
def asset_service_contract_detail(request, pk):
    obj = assets_object(
        request,
        AssetServiceContract,
        pk,
        select_related=["vendor", "fixed_asset", "operational_asset", "currency"],
    )
    linked_requests = obj.maintenance_requests.select_related("assigned_technician").order_by("-created_at")[:10]
    linked_logs = obj.maintenance_logs.select_related("lead_technician", "service_vendor").order_by("-service_date")[:10]

    context = {
        "service_contract": obj,
        "linked_requests": linked_requests,
        "linked_logs": linked_logs,
        "renew_form": AssetServiceContractRenewForm(
            initial={
                "new_end_date": obj.end_date + timedelta(days=365) if obj.end_date else timezone.now().date(),
                "new_contract_value": obj.contract_value,
            }
        ),
        "status_choices": AssetServiceContract.STATUS_CHOICES,
        "contract_type_choices": AssetServiceContract.CONTRACT_TYPE_CHOICES,
    }
    return render(request, "assets/asset_maintenance/asset_service_contract/detail.html", context)


@login_required
def asset_service_contract_create(request):
    if request.method == "POST":
        form = AssetServiceContractForm(request.POST, tenant=request.tenant)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Service Contract {obj.number} created successfully.")
            return redirect("assets:asset_service_contract_detail", pk=obj.pk)
    else:
        initial = {}
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id:
            initial["fixed_asset"] = fixed_asset_id
        vendor_id = request.GET.get("vendor")
        if vendor_id:
            initial["vendor"] = vendor_id
        form = AssetServiceContractForm(initial=initial, tenant=request.tenant)
        form.tenant = request.tenant

    context = {
        "form": form,
        "service_contract": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_maintenance/asset_service_contract/form.html", context)


@login_required
def asset_service_contract_edit(request, pk):
    obj = assets_object(request, AssetServiceContract, pk)
    if request.method == "POST":
        form = AssetServiceContractForm(request.POST, instance=obj, tenant=request.tenant)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Service Contract {obj.number} updated successfully.")
            return redirect("assets:asset_service_contract_detail", pk=obj.pk)
    else:
        form = AssetServiceContractForm(instance=obj, tenant=request.tenant)
        form.tenant = request.tenant

    context = {
        "form": form,
        "service_contract": obj,
        "is_edit": True,
    }
    return render(request, "assets/asset_maintenance/asset_service_contract/form.html", context)


@require_POST
@tenant_admin_required
def asset_service_contract_delete(request, pk):
    obj = assets_object(request, AssetServiceContract, pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Service Contract {number} deleted.")
    return redirect("assets:asset_service_contract_list")


@require_POST
@login_required
def asset_service_contract_activate(request, pk):
    obj = assets_object(request, AssetServiceContract, pk)
    obj.activate()
    write_audit_log(request.user, obj, "update", changes={"action": "activate"}, tenant=request.tenant)
    messages.success(request, f"Service Contract {obj.number} is now active.")
    return redirect("assets:asset_service_contract_detail", pk=obj.pk)


@require_POST
@login_required
def asset_service_contract_record_visit(request, pk):
    obj = assets_object(request, AssetServiceContract, pk)
    obj.record_visit()
    write_audit_log(
        request.user,
        obj,
        "update",
        changes={"action": "record_visit", "completed": obj.pm_visits_completed},
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"Logged maintenance visit for {obj.number}. Visits completed: {obj.pm_visits_completed} of {obj.pm_visits_included}.",
    )
    return redirect("assets:asset_service_contract_detail", pk=obj.pk)


@require_POST
@login_required
def asset_service_contract_renew(request, pk):
    obj = assets_object(request, AssetServiceContract, pk)
    form = AssetServiceContractRenewForm(request.POST)
    if form.is_valid():
        new_end = form.cleaned_data["new_end_date"]
        new_val = form.cleaned_data.get("new_contract_value")
        notes = form.cleaned_data.get("notes", "")
        obj.renew(new_end_date=new_end, new_contract_value=new_val, notes=notes)
        write_audit_log(
            request.user,
            obj,
            "update",
            changes={"action": "renew", "new_end_date": str(new_end), "notes": notes},
            tenant=request.tenant,
        )
        messages.success(request, f"Contract {obj.number} renewed until {new_end}.")
    else:
        messages.error(request, "Invalid contract renewal parameters.")
    return redirect("assets:asset_service_contract_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def asset_service_contract_terminate(request, pk):
    obj = assets_object(request, AssetServiceContract, pk)
    obj.terminate()
    write_audit_log(request.user, obj, "update", changes={"action": "terminate"}, tenant=request.tenant)
    messages.warning(request, f"Service Contract {obj.number} has been terminated.")
    return redirect("assets:asset_service_contract_detail", pk=obj.pk)
