from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetMaintenance.AssetMaintenanceRequests import (
    AssetMaintenanceRequestDispatchForm,
    AssetMaintenanceRequestForm,
    AssetMaintenanceRequestRejectForm,
    AssetMaintenanceRequestResolveForm,
    AssetMaintenanceRequestTriageForm,
)
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import AssetMaintenanceRequest
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_maintenance_request_list(request):
    qs = AssetMaintenanceRequest.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "requester", "department", "assigned_technician", "assigned_vendor"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(symptom_description__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_urgency = request.GET.get("urgency", "").strip()
    if selected_urgency:
        qs = qs.filter(urgency=selected_urgency)

    selected_type = request.GET.get("request_type", "").strip()
    if selected_type:
        qs = qs.filter(request_type=selected_type)

    is_breakdown = request.GET.get("is_breakdown", "").strip()
    if is_breakdown == "1":
        qs = qs.filter(is_breakdown=True)

    all_tenant_requests = AssetMaintenanceRequest.objects.filter(tenant=request.tenant)
    agg = all_tenant_requests.aggregate(
        total_requests=Count("id"),
        breakdown_count=Count("id", filter=Q(is_breakdown=True)),
        critical_count=Count("id", filter=Q(urgency="critical")),
        open_count=Count("id", filter=Q(status__in=["submitted", "triaged", "assigned", "in_progress"])),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "maintenance_requests": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": q,
        "status_choices": AssetMaintenanceRequest.STATUS_CHOICES,
        "urgency_choices": AssetMaintenanceRequest.URGENCY_CHOICES,
        "request_type_choices": AssetMaintenanceRequest.REQUEST_TYPE_CHOICES,
        "total_requests": agg["total_requests"] or 0,
        "breakdown_count": agg["breakdown_count"] or 0,
        "critical_count": agg["critical_count"] or 0,
        "open_count": agg["open_count"] or 0,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_request/list.html", context)


@login_required
def asset_maintenance_request_detail(request, pk):
    obj = assets_object(
        request,
        AssetMaintenanceRequest,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "requester",
            "department",
            "assigned_technician",
            "assigned_vendor",
            "service_contract",
            "dispatched_work_order",
            "resolved_by",
        ],
    )
    linked_logs = getattr(obj, "maintenance_logs", None)
    if linked_logs is not None:
        logs_qs = linked_logs.select_related("lead_technician", "service_vendor").order_by("-service_date")
    else:
        logs_qs = []

    context = {
        "maintenance_request": obj,
        "linked_logs": logs_qs,
        "triage_form": AssetMaintenanceRequestTriageForm(initial={"urgency": obj.urgency, "triage_notes": obj.triage_notes}),
        "dispatch_form": AssetMaintenanceRequestDispatchForm(
            request.tenant,
            initial={
                "assigned_technician": obj.assigned_technician,
                "assigned_vendor": obj.assigned_vendor,
                "service_contract": obj.service_contract,
                "dispatched_work_order": obj.dispatched_work_order,
            },
        ),
        "resolve_form": AssetMaintenanceRequestResolveForm(),
        "reject_form": AssetMaintenanceRequestRejectForm(),
        "status_choices": AssetMaintenanceRequest.STATUS_CHOICES,
        "urgency_choices": AssetMaintenanceRequest.URGENCY_CHOICES,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_request/detail.html", context)


@login_required
def asset_maintenance_request_create(request):
    if request.method == "POST":
        form = AssetMaintenanceRequestForm(request.POST, tenant=request.tenant)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.requester:
                obj.requester = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Maintenance Request {obj.number} submitted successfully.")
            return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)
    else:
        initial = {}
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id:
            initial["fixed_asset"] = fixed_asset_id
        operational_asset_id = request.GET.get("operational_asset")
        if operational_asset_id:
            initial["operational_asset"] = operational_asset_id
        form = AssetMaintenanceRequestForm(initial=initial, tenant=request.tenant)
        form.tenant = request.tenant

    context = {
        "form": form,
        "maintenance_request": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_request/form.html", context)


@login_required
def asset_maintenance_request_edit(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    if request.method == "POST":
        form = AssetMaintenanceRequestForm(request.POST, instance=obj, tenant=request.tenant)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Maintenance Request {obj.number} updated successfully.")
            return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)
    else:
        form = AssetMaintenanceRequestForm(instance=obj, tenant=request.tenant)
        form.tenant = request.tenant

    context = {
        "form": form,
        "maintenance_request": obj,
        "is_edit": True,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_request/form.html", context)


@require_POST
@tenant_admin_required
def asset_maintenance_request_delete(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Maintenance Request {number} was deleted.")
    return redirect("assets:asset_maintenance_request_list")


@require_POST
@login_required
def asset_maintenance_request_triage(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    form = AssetMaintenanceRequestTriageForm(request.POST)
    if form.is_valid():
        obj.triage(
            urgency=form.cleaned_data["urgency"],
            triage_notes=form.cleaned_data["triage_notes"],
        )
        write_audit_log(request.user, obj, "update", changes={"action": "triage"}, tenant=request.tenant)
        messages.success(request, f"Request {obj.number} has been triaged.")
    else:
        messages.error(request, "Invalid triage data submitted.")
    return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_request_dispatch(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    form = AssetMaintenanceRequestDispatchForm(request.tenant, request.POST)
    if form.is_valid():
        obj.dispatch(
            technician=form.cleaned_data.get("assigned_technician"),
            vendor=form.cleaned_data.get("assigned_vendor"),
            service_contract=form.cleaned_data.get("service_contract"),
            work_order=form.cleaned_data.get("dispatched_work_order"),
        )
        write_audit_log(request.user, obj, "update", changes={"action": "dispatch"}, tenant=request.tenant)
        messages.success(request, f"Request {obj.number} dispatched successfully.")
    else:
        messages.error(request, "Invalid dispatch assignment data.")
    return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_request_start(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    obj.start_work()
    write_audit_log(request.user, obj, "update", changes={"action": "start_work"}, tenant=request.tenant)
    messages.success(request, f"Work on Request {obj.number} has started.")
    return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_request_resolve(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    form = AssetMaintenanceRequestResolveForm(request.POST)
    if form.is_valid():
        obj.resolve(
            user=request.user,
            summary=form.cleaned_data["resolution_summary"],
        )
        write_audit_log(request.user, obj, "update", changes={"action": "resolve"}, tenant=request.tenant)
        messages.success(request, f"Request {obj.number} resolved successfully.")
    else:
        messages.error(request, "Resolution summary is required.")
    return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_request_close(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    obj.close()
    write_audit_log(request.user, obj, "update", changes={"action": "close"}, tenant=request.tenant)
    messages.success(request, f"Request {obj.number} has been closed.")
    return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_request_reject(request, pk):
    obj = assets_object(request, AssetMaintenanceRequest, pk)
    form = AssetMaintenanceRequestRejectForm(request.POST)
    if form.is_valid():
        obj.reject(reason=form.cleaned_data["rejection_reason"])
        write_audit_log(request.user, obj, "update", changes={"action": "reject"}, tenant=request.tenant)
        messages.warning(request, f"Request {obj.number} has been rejected.")
    else:
        messages.error(request, "Rejection reason is required.")
    return redirect("assets:asset_maintenance_request_detail", pk=obj.pk)
