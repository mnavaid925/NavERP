from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetMaintenance.AssetMaintenanceSchedules import (
    AssetMaintenanceScheduleCompletionForm,
    AssetMaintenanceScheduleForm,
)
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import AssetMaintenanceRequest
from apps.assets.models.AssetMaintenance.AssetMaintenanceSchedules import AssetMaintenanceSchedule
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_maintenance_schedule_list(request):
    qs = AssetMaintenanceSchedule.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "asset_category", "assigned_technician", "preferred_vendor"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(service_checklist__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_type = request.GET.get("schedule_type", "").strip()
    if selected_type:
        qs = qs.filter(schedule_type=selected_type)

    selected_unit = request.GET.get("frequency_unit", "").strip()
    if selected_unit:
        qs = qs.filter(frequency_unit=selected_unit)

    today = timezone.now().date()
    all_tenant_schedules = AssetMaintenanceSchedule.objects.filter(tenant=request.tenant)
    agg = all_tenant_schedules.aggregate(
        total_schedules=Count("id"),
        active_count=Count("id", filter=Q(is_active=True, status="active")),
        overdue_count=Count("id", filter=Q(is_active=True, next_due_date__lt=today)),
        paused_count=Count("id", filter=Q(status="paused")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "maintenance_schedules": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetMaintenanceSchedule.STATUS_CHOICES,
        "schedule_type_choices": AssetMaintenanceSchedule.SCHEDULE_TYPE_CHOICES,
        "frequency_unit_choices": AssetMaintenanceSchedule.FREQUENCY_UNIT_CHOICES,
        "total_schedules": agg["total_schedules"] or 0,
        "active_count": agg["active_count"] or 0,
        "overdue_count": agg["overdue_count"] or 0,
        "paused_count": agg["paused_count"] or 0,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_schedule/list.html", context)


@login_required
def asset_maintenance_schedule_detail(request, pk):
    obj = assets_object(
        request,
        AssetMaintenanceSchedule,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "assigned_technician",
            "preferred_vendor",
            "service_contract",
        ],
    )
    linked_requests = obj.maintenance_requests.select_related("assigned_technician").order_by("-created_at")[:10]
    linked_logs = obj.maintenance_logs.select_related("lead_technician", "service_vendor").order_by("-service_date")[:10]

    context = {
        "maintenance_schedule": obj,
        "service_checklist_items": obj.checklist_items(),
        "completion_form": AssetMaintenanceScheduleCompletionForm(
            initial={"completion_meter": obj.last_service_meter}
        ),
        "linked_requests": linked_requests,
        "linked_logs": linked_logs,
        "status_choices": AssetMaintenanceSchedule.STATUS_CHOICES,
        "schedule_type_choices": AssetMaintenanceSchedule.SCHEDULE_TYPE_CHOICES,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_schedule/detail.html", context)


@login_required
def asset_maintenance_schedule_create(request):
    if request.method == "POST":
        form = AssetMaintenanceScheduleForm(request.POST)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.next_due_date:
                obj.recalculate_next_due()
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Maintenance Schedule {obj.number} created successfully.")
            return redirect("assets:asset_maintenance_schedule_detail", pk=obj.pk)
    else:
        initial = {}
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id:
            initial["fixed_asset"] = fixed_asset_id
        operational_asset_id = request.GET.get("operational_asset")
        if operational_asset_id:
            initial["operational_asset"] = operational_asset_id
        form = AssetMaintenanceScheduleForm(initial=initial)
        form.tenant = request.tenant

    context = {
        "form": form,
        "maintenance_schedule": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_schedule/form.html", context)


@login_required
def asset_maintenance_schedule_edit(request, pk):
    obj = assets_object(request, AssetMaintenanceSchedule, pk)
    if request.method == "POST":
        form = AssetMaintenanceScheduleForm(request.POST, instance=obj)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Maintenance Schedule {obj.number} updated successfully.")
            return redirect("assets:asset_maintenance_schedule_detail", pk=obj.pk)
    else:
        form = AssetMaintenanceScheduleForm(instance=obj)
        form.tenant = request.tenant

    context = {
        "form": form,
        "maintenance_schedule": obj,
        "is_edit": True,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_schedule/form.html", context)


@require_POST
@tenant_admin_required
def asset_maintenance_schedule_delete(request, pk):
    obj = assets_object(request, AssetMaintenanceSchedule, pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Maintenance Schedule {number} deleted.")
    return redirect("assets:asset_maintenance_schedule_list")


@require_POST
@login_required
def asset_maintenance_schedule_activate(request, pk):
    obj = assets_object(request, AssetMaintenanceSchedule, pk)
    obj.activate()
    write_audit_log(request.user, obj, "update", changes={"action": "activate"}, tenant=request.tenant)
    messages.success(request, f"Maintenance Schedule {obj.number} is now active.")
    return redirect("assets:asset_maintenance_schedule_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_schedule_pause(request, pk):
    obj = assets_object(request, AssetMaintenanceSchedule, pk)
    obj.pause()
    write_audit_log(request.user, obj, "update", changes={"action": "pause"}, tenant=request.tenant)
    messages.warning(request, f"Maintenance Schedule {obj.number} has been paused.")
    return redirect("assets:asset_maintenance_schedule_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_schedule_generate_request(request, pk):
    obj = assets_object(request, AssetMaintenanceSchedule, pk)
    new_req = AssetMaintenanceRequest.objects.create(
        tenant=request.tenant,
        title=f"PM: {obj.name}",
        fixed_asset=obj.fixed_asset,
        operational_asset=obj.operational_asset,
        requester=request.user,
        request_type="preventive_inspection",
        urgency="medium",
        assigned_technician=obj.assigned_technician,
        assigned_vendor=obj.preferred_vendor,
        service_contract=obj.service_contract,
        symptom_description=f"Scheduled preventive service per {obj.number} ({obj.name}).\n\nChecklist:\n{obj.service_checklist or 'Standard inspection'}",
        status="assigned" if (obj.assigned_technician or obj.preferred_vendor) else "submitted",
    )
    write_audit_log(request.user, new_req, "create", changes={"source_schedule": obj.number}, tenant=request.tenant)
    messages.success(request, f"Generated Maintenance Request {new_req.number} from schedule {obj.number}.")
    return redirect("assets:asset_maintenance_request_detail", pk=new_req.pk)


@require_POST
@login_required
def asset_maintenance_schedule_record_completion(request, pk):
    obj = assets_object(request, AssetMaintenanceSchedule, pk)
    form = AssetMaintenanceScheduleCompletionForm(request.POST)
    if form.is_valid():
        comp_date = form.cleaned_data["completion_date"]
        comp_meter = form.cleaned_data.get("completion_meter")
        obj.record_completion(completion_date=comp_date, completion_meter=comp_meter, user=request.user)
        write_audit_log(
            request.user,
            obj,
            "update",
            changes={
                "action": "record_completion",
                "completed_date": str(comp_date),
                "next_due_date": str(obj.next_due_date),
            },
            tenant=request.tenant,
        )
        messages.success(
            request,
            f"Service completion recorded for {obj.number}. Next service due on {obj.next_due_date}.",
        )
    else:
        messages.error(request, "Invalid completion details.")
    return redirect("assets:asset_maintenance_schedule_detail", pk=obj.pk)
