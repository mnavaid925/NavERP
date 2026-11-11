from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.MobileAssetManagement.FieldWorkOrders import FieldWorkOrderForm
from apps.assets.models.MobileAssetManagement.FieldWorkOrders import FieldWorkOrder
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def field_work_order_list(request):
    qs = assets_scope(
        FieldWorkOrder.objects.select_related(
            "asset", "fixed_asset", "assigned_technician", "maintenance_request"
        ).defer("parts_requisition_notes", "work_performed_notes"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
            | Q(assigned_technician__first_name__icontains=q)
            | Q(assigned_technician__last_name__icontains=q)
            | Q(assigned_technician__username__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    priority_filter = request.GET.get("priority", "").strip()
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    type_filter = request.GET.get("work_order_type", "").strip()
    if type_filter:
        qs = qs.filter(work_order_type=type_filter)

    metrics = FieldWorkOrder.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=["en_route", "on_site", "in_progress"])),
        completed=Count("id", filter=Q(status="completed")),
        urgent=Count("id", filter=Q(priority="urgent")),
        wrench_minutes=Sum("labor_wrench_minutes"),
    )
    total_work_orders = metrics["total"]
    active_count = metrics["active"]
    completed_count = metrics["completed"]
    urgent_count = metrics["urgent"]
    total_wrench_hours = round((metrics["wrench_minutes"] or 0) / 60.0, 1)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/mobileassetmanagement/field_work_order/list.html",
        {
            "work_orders": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": FieldWorkOrder.STATUS_CHOICES,
            "priority_choices": FieldWorkOrder.PRIORITY_CHOICES,
            "type_choices": FieldWorkOrder.WORK_ORDER_TYPE_CHOICES,
            "total_work_orders": total_work_orders,
            "active_count": active_count,
            "completed_count": completed_count,
            "urgent_count": urgent_count,
            "total_wrench_hours": total_wrench_hours,
        },
    )


@login_required
def field_work_order_create(request):
    if request.method == "POST":
        form = FieldWorkOrderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            work_order = form.save(commit=False)
            work_order.tenant = request.tenant
            if not work_order.assigned_technician_id:
                work_order.assigned_technician = request.user
            now = timezone.now()
            if work_order.status in ["on_site", "in_progress", "completed"] and not work_order.actual_arrival:
                work_order.actual_arrival = now
            if work_order.status == "completed" and not work_order.completed_at:
                work_order.completed_at = now
            if work_order.signature_name and not work_order.signed_at:
                work_order.signed_at = now
            if work_order.is_offline_captured and not work_order.synced_at:
                work_order.synced_at = now
            work_order.save()
            write_audit_log(request.user, work_order, "create", tenant=request.tenant)
            messages.success(request, f"Field work order {work_order.number} created successfully.")
            return redirect("assets:field_work_order_detail", pk=work_order.pk)
    else:
        initial = {"assigned_technician": request.user, "scheduled_start": timezone.now()}
        form = FieldWorkOrderForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/mobileassetmanagement/field_work_order/form.html",
        {"form": form, "title": "New Field Work Order"},
    )


@login_required
def field_work_order_detail(request, pk):
    work_order = assets_object(
        request,
        FieldWorkOrder,
        pk,
        select_related=["asset", "fixed_asset", "assigned_technician", "maintenance_request"],
    )
    return render(
        request,
        "assets/mobileassetmanagement/field_work_order/detail.html",
        {"work_order": work_order},
    )


@login_required
def field_work_order_edit(request, pk):
    work_order = assets_object(request, FieldWorkOrder, pk)
    if request.method == "POST":
        form = FieldWorkOrderForm(request.POST, instance=work_order, tenant=request.tenant)
        if form.is_valid():
            work_order = form.save(commit=False)
            now = timezone.now()
            if work_order.status in ["on_site", "in_progress", "completed"] and not work_order.actual_arrival:
                work_order.actual_arrival = now
            if work_order.status == "completed" and not work_order.completed_at:
                work_order.completed_at = now
            if work_order.signature_name and not work_order.signed_at:
                work_order.signed_at = now
            if work_order.is_offline_captured and not work_order.synced_at:
                work_order.synced_at = now
            work_order.save()
            write_audit_log(request.user, work_order, "update", tenant=request.tenant)
            messages.success(request, f"Field work order {work_order.number} updated successfully.")
            return redirect("assets:field_work_order_detail", pk=work_order.pk)
    else:
        form = FieldWorkOrderForm(instance=work_order, tenant=request.tenant)

    return render(
        request,
        "assets/mobileassetmanagement/field_work_order/form.html",
        {"form": form, "work_order": work_order, "title": f"Edit Work Order: {work_order.number}"},
    )


@login_required
@require_POST
def field_work_order_delete(request, pk):
    work_order = assets_object(request, FieldWorkOrder, pk)
    number = work_order.number
    try:
        with transaction.atomic():
            write_audit_log(request.user, work_order, "delete", tenant=request.tenant)
            work_order.delete()
        messages.success(request, f"Field work order {number} deleted successfully.")
    except ProtectedError:
        messages.error(request, f"Cannot delete field work order {number}: dependent records exist.")
    return redirect("assets:field_work_order_list")
