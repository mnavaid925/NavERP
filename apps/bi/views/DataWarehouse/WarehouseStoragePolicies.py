from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicyForm
from apps.bi.models.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicy
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def warehouse_storage_policy_list(request):
    queryset = bi_scope(WarehouseStoragePolicy.objects.all(), request)

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(partition_key__icontains=q)
            | Q(description__icontains=q)
        )

    strategy_filter = request.GET.get("partition_strategy", "").strip()
    if strategy_filter:
        queryset = queryset.filter(partition_strategy=strategy_filter)

    codec_filter = request.GET.get("compression_codec", "").strip()
    if codec_filter:
        queryset = queryset.filter(compression_codec=codec_filter)

    vacuum_filter = request.GET.get("vacuum_cadence", "").strip()
    if vacuum_filter:
        queryset = queryset.filter(vacuum_cadence=vacuum_filter)

    active_filter = request.GET.get("is_active", "").strip()
    if active_filter == "1":
        queryset = queryset.filter(is_active=True)
    elif active_filter == "0":
        queryset = queryset.filter(is_active=False)

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(p.number),
                csv_safe(p.name),
                csv_safe(p.get_partition_strategy_display()),
                csv_safe(p.partition_key),
                csv_safe(p.get_partition_granularity_display()),
                csv_safe(p.get_compression_codec_display()),
                csv_safe(p.hot_tier_days),
                csv_safe(p.warm_tier_days),
                csv_safe(p.cold_tier_days),
                csv_safe(p.time_travel_days),
                csv_safe("Yes" if p.auto_purge_enabled else "No"),
                csv_safe(p.get_vacuum_cadence_display()),
                csv_safe("Yes" if p.is_default else "No"),
                csv_safe("Yes" if p.is_active else "No"),
                csv_safe(p.created_at.isoformat() if p.created_at else ""),
            ]
            for p in queryset
        ]
        return csv_export_response(
            request,
            filename="warehouse_storage_policies.csv",
            headers=[
                "Number",
                "Name",
                "Partition Strategy",
                "Partition Key",
                "Granularity",
                "Compression",
                "Hot Days",
                "Warm Days",
                "Cold Days",
                "Time Travel Days",
                "Auto Purge",
                "Vacuum Cadence",
                "Default",
                "Active",
                "Created At",
            ],
            rows=rows,
        )

    total_count = WarehouseStoragePolicy.objects.filter(tenant=request.tenant).count()
    default_policy = WarehouseStoragePolicy.objects.filter(tenant=request.tenant, is_default=True).first()

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    active_choices = [("1", "Active"), ("0", "Inactive")]

    return render(
        request,
        "bi/data_warehouse/warehouse_storage_policy/list.html",
        {
            "page_obj": page_obj,
            "storage_policies": page_obj.object_list,
            "partition_strategy_choices": WarehouseStoragePolicy.PARTITION_STRATEGY_CHOICES,
            "compression_codec_choices": WarehouseStoragePolicy.COMPRESSION_CODEC_CHOICES,
            "vacuum_cadence_choices": WarehouseStoragePolicy.VACUUM_CADENCE_CHOICES,
            "active_choices": active_choices,
            "total_count": total_count,
            "default_policy": default_policy,
            "search_query": q,
        },
    )


@login_required
def warehouse_storage_policy_detail(request, pk):
    policy = bi_object(request, WarehouseStoragePolicy, pk)
    tables = policy.tables.filter(tenant=request.tenant).select_related("lakehouse_zone", "data_mart")
    return render(
        request,
        "bi/data_warehouse/warehouse_storage_policy/detail.html",
        {
            "storage_policy": policy,
            "policy": policy,
            "tables": tables,
        },
    )


@login_required
@tenant_admin_required
def warehouse_storage_policy_create(request):
    if request.method == "POST":
        form = WarehouseStoragePolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                policy = form.save(commit=False)
                policy.tenant = request.tenant
                if policy.is_default:
                    WarehouseStoragePolicy.objects.filter(tenant=request.tenant, is_default=True).update(is_default=False)
                policy.save()
            write_audit_log(request.user, policy, "create", tenant=request.tenant)
            messages.success(request, f"Storage Policy '{policy.name}' created successfully.")
            return redirect("bi:warehouse_storage_policy_detail", pk=policy.pk)
    else:
        form = WarehouseStoragePolicyForm(tenant=request.tenant)

    return render(
        request,
        "bi/data_warehouse/warehouse_storage_policy/form.html",
        {
            "form": form,
            "storage_policy": None,
            "policy": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def warehouse_storage_policy_edit(request, pk):
    policy = bi_object(request, WarehouseStoragePolicy, pk)
    if request.method == "POST":
        form = WarehouseStoragePolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                updated = form.save(commit=False)
                if updated.is_default:
                    WarehouseStoragePolicy.objects.filter(tenant=request.tenant, is_default=True).exclude(pk=policy.pk).update(is_default=False)
                updated.save()
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Storage Policy '{updated.name}' updated successfully.")
            return redirect("bi:warehouse_storage_policy_detail", pk=updated.pk)
    else:
        form = WarehouseStoragePolicyForm(instance=policy, tenant=request.tenant)

    return render(
        request,
        "bi/data_warehouse/warehouse_storage_policy/form.html",
        {
            "form": form,
            "storage_policy": policy,
            "policy": policy,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def warehouse_storage_policy_delete(request, pk):
    policy = bi_object(request, WarehouseStoragePolicy, pk)
    policy_name = policy.name
    write_audit_log(request.user, policy, "delete", tenant=request.tenant)
    policy.delete()
    messages.success(request, f"Storage Policy '{policy_name}' was deleted.")
    return redirect("bi:warehouse_storage_policy_list")
