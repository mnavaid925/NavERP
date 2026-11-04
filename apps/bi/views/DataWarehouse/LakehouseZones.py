from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataWarehouse.LakehouseZones import LakehouseZoneForm
from apps.bi.models.DataWarehouse.LakehouseZones import LakehouseZone
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def lakehouse_zone_list(request):
    queryset = bi_scope(LakehouseZone.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(base_uri_path__icontains=q)
            | Q(description__icontains=q)
        )

    zone_filter = request.GET.get("zone_type", "").strip()
    if zone_filter:
        queryset = queryset.filter(zone_type=zone_filter)

    backend_filter = request.GET.get("storage_backend", "").strip()
    if backend_filter:
        queryset = queryset.filter(storage_backend=backend_filter)

    format_filter = request.GET.get("default_format", "").strip()
    if format_filter:
        queryset = queryset.filter(default_format=format_filter)

    active_filter = request.GET.get("is_active", "").strip()
    if active_filter == "1":
        queryset = queryset.filter(is_active=True)
    elif active_filter == "0":
        queryset = queryset.filter(is_active=False)

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(z.number),
                csv_safe(z.name),
                csv_safe(z.code),
                csv_safe(z.get_zone_type_display()),
                csv_safe(z.get_storage_backend_display()),
                csv_safe(z.get_default_format_display()),
                csv_safe(z.base_uri_path),
                csv_safe("Yes" if z.is_read_only else "No"),
                csv_safe("Yes" if z.is_active else "No"),
                csv_safe(z.created_at.isoformat() if z.created_at else ""),
            ]
            for z in queryset
        ]
        return csv_export_response(
            request,
            filename="lakehouse_zones.csv",
            headers=[
                "Number",
                "Name",
                "Code",
                "Zone Type",
                "Storage Backend",
                "Default Format",
                "Base URI Path",
                "Read Only",
                "Active",
                "Created At",
            ],
            rows=rows,
        )

    counts = LakehouseZone.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        bronze=Count("id", filter=Q(zone_type="bronze")),
        silver=Count("id", filter=Q(zone_type="silver")),
        gold=Count("id", filter=Q(zone_type="gold")),
    )

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    active_choices = [("1", "Active"), ("0", "Inactive")]

    return render(
        request,
        "bi/data_warehouse/lakehouse_zone/list.html",
        {
            "page_obj": page_obj,
            "lakehouse_zones": page_obj.object_list,
            "zone_type_choices": LakehouseZone.ZONE_TYPE_CHOICES,
            "storage_backend_choices": LakehouseZone.STORAGE_BACKEND_CHOICES,
            "default_format_choices": LakehouseZone.DEFAULT_FORMAT_CHOICES,
            "active_choices": active_choices,
            "total_count": counts["total"],
            "bronze_count": counts["bronze"],
            "silver_count": counts["silver"],
            "gold_count": counts["gold"],
            "search_query": q,
        },
    )


@login_required
def lakehouse_zone_detail(request, pk):
    zone = bi_object(request, LakehouseZone, pk)
    tables = zone.tables.filter(tenant=request.tenant).select_related("data_mart", "storage_policy")
    return render(
        request,
        "bi/data_warehouse/lakehouse_zone/detail.html",
        {
            "lakehouse_zone": zone,
            "tables": tables,
        },
    )


@login_required
@tenant_admin_required
def lakehouse_zone_create(request):
    if request.method == "POST":
        form = LakehouseZoneForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            zone = form.save(commit=False)
            zone.tenant = request.tenant
            zone.save()
            write_audit_log(request.user, zone, "create", tenant=request.tenant)
            messages.success(request, f"Lakehouse Zone '{zone.name}' created successfully.")
            return redirect("bi:lakehouse_zone_detail", pk=zone.pk)
    else:
        form = LakehouseZoneForm(tenant=request.tenant)

    return render(
        request,
        "bi/data_warehouse/lakehouse_zone/form.html",
        {
            "form": form,
            "lakehouse_zone": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def lakehouse_zone_edit(request, pk):
    zone = bi_object(request, LakehouseZone, pk)
    if request.method == "POST":
        form = LakehouseZoneForm(request.POST, instance=zone, tenant=request.tenant)
        if form.is_valid():
            updated = form.save()
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Lakehouse Zone '{updated.name}' updated successfully.")
            return redirect("bi:lakehouse_zone_detail", pk=updated.pk)
    else:
        form = LakehouseZoneForm(instance=zone, tenant=request.tenant)

    return render(
        request,
        "bi/data_warehouse/lakehouse_zone/form.html",
        {
            "form": form,
            "lakehouse_zone": zone,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def lakehouse_zone_delete(request, pk):
    zone = bi_object(request, LakehouseZone, pk)
    zone_name = zone.name
    try:
        write_audit_log(request.user, zone, "delete", tenant=request.tenant)
        zone.delete()
        messages.success(request, f"Lakehouse Zone '{zone_name}' was deleted.")
    except ProtectedError:
        messages.error(
            request,
            f"Cannot delete Lakehouse Zone '{zone_name}' because one or more warehouse tables reside in this zone.",
        )
        return redirect("bi:lakehouse_zone_detail", pk=zone.pk)
    return redirect("bi:lakehouse_zone_list")
