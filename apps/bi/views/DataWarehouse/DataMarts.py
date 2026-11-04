from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataWarehouse.DataMarts import DataMartForm
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def data_mart_list(request):
    queryset = bi_scope(DataMart.objects.all(), request).select_related("org_unit", "owner", "steward")

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    subject_filter = request.GET.get("subject_area", "").strip()
    if subject_filter:
        queryset = queryset.filter(subject_area=subject_filter)

    cert_filter = request.GET.get("certification_status", "").strip()
    if cert_filter:
        queryset = queryset.filter(certification_status=cert_filter)

    access_filter = request.GET.get("access_tier", "").strip()
    if access_filter:
        queryset = queryset.filter(access_tier=access_filter)

    active_filter = request.GET.get("is_active", "").strip()
    if active_filter == "1":
        queryset = queryset.filter(is_active=True)
    elif active_filter == "0":
        queryset = queryset.filter(is_active=False)

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(m.number),
                csv_safe(m.name),
                csv_safe(m.code),
                csv_safe(m.get_subject_area_display()),
                csv_safe(m.org_unit.name if m.org_unit else ""),
                csv_safe(m.owner.username if m.owner else ""),
                csv_safe(m.steward.username if m.steward else ""),
                csv_safe(m.get_access_tier_display()),
                csv_safe(m.get_certification_status_display()),
                csv_safe(m.get_refresh_cadence_display()),
                csv_safe("Yes" if m.is_active else "No"),
                csv_safe(m.created_at.isoformat() if m.created_at else ""),
            ]
            for m in queryset
        ]
        return csv_export_response(
            request,
            filename="data_marts.csv",
            headers=[
                "Number",
                "Name",
                "Code",
                "Subject Area",
                "Org Unit",
                "Owner",
                "Steward",
                "Access Tier",
                "Certification Status",
                "Refresh Cadence",
                "Active",
                "Created At",
            ],
            rows=rows,
        )

    counts = DataMart.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        certified=Count("id", filter=Q(certification_status="certified")),
        draft=Count("id", filter=Q(certification_status="draft")),
    )

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    active_choices = [("1", "Active"), ("0", "Inactive")]

    return render(
        request,
        "bi/data_warehouse/data_mart/list.html",
        {
            "page_obj": page_obj,
            "data_marts": page_obj.object_list,
            "subject_area_choices": DataMart.SUBJECT_AREA_CHOICES,
            "certification_status_choices": DataMart.CERTIFICATION_STATUS_CHOICES,
            "access_tier_choices": DataMart.ACCESS_TIER_CHOICES,
            "active_choices": active_choices,
            "total_count": counts["total"],
            "certified_count": counts["certified"],
            "draft_count": counts["draft"],
            "search_query": q,
        },
    )


@login_required
def data_mart_detail(request, pk):
    mart = bi_object(
        request,
        DataMart,
        pk,
        select_related=("org_unit", "owner", "steward"),
    )
    tables = mart.tables.filter(tenant=request.tenant).select_related("lakehouse_zone", "storage_policy")
    return render(
        request,
        "bi/data_warehouse/data_mart/detail.html",
        {
            "data_mart": mart,
            "tables": tables,
        },
    )


@login_required
@tenant_admin_required
def data_mart_create(request):
    if request.method == "POST":
        form = DataMartForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            mart = form.save(commit=False)
            mart.tenant = request.tenant
            mart.save()
            write_audit_log(request.user, mart, "create", tenant=request.tenant)
            messages.success(request, f"Data Mart '{mart.name}' created successfully.")
            return redirect("bi:data_mart_detail", pk=mart.pk)
    else:
        form = DataMartForm(tenant=request.tenant)

    return render(
        request,
        "bi/data_warehouse/data_mart/form.html",
        {
            "form": form,
            "data_mart": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def data_mart_edit(request, pk):
    mart = bi_object(request, DataMart, pk)
    if request.method == "POST":
        form = DataMartForm(request.POST, instance=mart, tenant=request.tenant)
        if form.is_valid():
            updated = form.save()
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Data Mart '{updated.name}' updated successfully.")
            return redirect("bi:data_mart_detail", pk=updated.pk)
    else:
        form = DataMartForm(instance=mart, tenant=request.tenant)

    return render(
        request,
        "bi/data_warehouse/data_mart/form.html",
        {
            "form": form,
            "data_mart": mart,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def data_mart_delete(request, pk):
    mart = bi_object(request, DataMart, pk)
    mart_name = mart.name
    write_audit_log(request.user, mart, "delete", tenant=request.tenant)
    mart.delete()
    messages.success(request, f"Data Mart '{mart_name}' was deleted.")
    return redirect("bi:data_mart_list")
