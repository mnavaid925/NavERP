from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetInventoryTracking.AssetMovementLogs import AssetMovementLogForm
from apps.assets.models.AssetInventoryTracking.AssetMovementLogs import AssetMovementLog
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.scm.models import Asset, Location


@login_required
def asset_movement_log_list(request):
    qs = AssetMovementLog.objects.filter(tenant=request.tenant).select_related(
        "asset",
        "from_location",
        "to_location",
        "from_org_unit",
        "to_org_unit",
        "from_custodian",
        "to_custodian",
        "dispatched_by",
        "received_by",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset__number__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(tracking_number__icontains=q)
            | Q(carrier_name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    movement_type = request.GET.get("movement_type", "").strip()
    if movement_type:
        qs = qs.filter(movement_type=movement_type)

    location_id = request.GET.get("location", "").strip()
    if location_id and location_id.isdigit():
        qs = qs.filter(Q(from_location_id=int(location_id)) | Q(to_location_id=int(location_id)))

    asset_id = request.GET.get("asset", "").strip()
    if asset_id and asset_id.isdigit():
        qs = qs.filter(asset_id=int(asset_id))

    all_tenant_movs = AssetMovementLog.objects.filter(tenant=request.tenant)
    counts = all_tenant_movs.aggregate(
        total=Count("id"),
        in_transit=Count("id", filter=Q(status__in=["dispatched", "in_transit"])),
        received=Count("id", filter=Q(status="received")),
        requested=Count("id", filter=Q(status="requested")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    locations = Location.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    assets = Asset.objects.filter(tenant=request.tenant).order_by("number")

    context = {
        "movements": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "locations": locations,
        "org_units": org_units,
        "assets": assets,
        "type_choices": AssetMovementLog.MOVEMENT_TYPE_CHOICES,
        "status_choices": AssetMovementLog.STATUS_CHOICES,
        "condition_choices": AssetMovementLog.CONDITION_CHOICES,
        "q": q,
        "total_count": counts["total"] or 0,
        "in_transit_count": counts["in_transit"] or 0,
        "received_count": counts["received"] or 0,
        "requested_count": counts["requested"] or 0,
    }
    return render(request, "assets/asset_inventory_tracking/asset_movement_log/list.html", context)


@login_required
def asset_movement_log_detail(request, pk):
    movement = get_object_or_404(
        AssetMovementLog.objects.select_related(
            "asset",
            "from_location",
            "to_location",
            "from_org_unit",
            "to_org_unit",
            "from_custodian",
            "to_custodian",
            "dispatched_by",
            "received_by",
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(request, "assets/asset_inventory_tracking/asset_movement_log/detail.html", {"movement": movement})


@login_required
def asset_movement_log_create(request):
    if request.method == "POST":
        form = AssetMovementLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                form.save_m2m()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Asset movement request {obj.number} created successfully.")
            return redirect("assets:asset_movement_log_detail", pk=obj.pk)
    else:
        initial = {}
        asset_id = request.GET.get("asset", "").strip()
        if asset_id and asset_id.isdigit():
            if Asset.objects.filter(pk=int(asset_id), tenant=request.tenant).exists():
                initial["asset"] = int(asset_id)
        form = AssetMovementLogForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_movement_log/form.html",
        {"form": form, "movement": None, "is_edit": False},
    )


@login_required
def asset_movement_log_edit(request, pk):
    movement = get_object_or_404(AssetMovementLog, pk=pk, tenant=request.tenant)
    if movement.status not in ("draft", "requested"):
        messages.error(request, f"Transfer {movement.number} is in status '{movement.get_status_display()}' and cannot be edited.")
        return redirect("assets:asset_movement_log_detail", pk=movement.pk)

    if request.method == "POST":
        form = AssetMovementLogForm(request.POST, instance=movement, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Asset movement {obj.number} updated successfully.")
            return redirect("assets:asset_movement_log_detail", pk=obj.pk)
    else:
        form = AssetMovementLogForm(instance=movement, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_movement_log/form.html",
        {"form": form, "movement": movement, "is_edit": True},
    )


@login_required
@require_POST
def asset_movement_log_delete(request, pk):
    movement = get_object_or_404(AssetMovementLog, pk=pk, tenant=request.tenant)
    if movement.status not in ("draft", "cancelled"):
        messages.error(request, f"Cannot delete movement in '{movement.get_status_display()}' status.")
        return redirect("assets:asset_movement_log_detail", pk=movement.pk)

    num = movement.number
    with transaction.atomic():
        write_audit_log(request.user, movement, "delete", tenant=request.tenant)
        movement.delete()
    messages.success(request, f"Movement record {num} deleted.")
    return redirect("assets:asset_movement_log_list")


@login_required
@require_POST
def asset_movement_log_dispatch(request, pk):
    movement = get_object_or_404(AssetMovementLog, pk=pk, tenant=request.tenant)
    if movement.status not in ("draft", "requested"):
        messages.error(request, f"Cannot dispatch transfer in '{movement.get_status_display()}' state.")
        return redirect("assets:asset_movement_log_detail", pk=movement.pk)

    with transaction.atomic():
        movement.status = "dispatched"
        movement.dispatch_date = timezone.now()
        movement.dispatched_by = request.user
        movement.save(update_fields=["status", "dispatch_date", "dispatched_by", "updated_at"])
        write_audit_log(request.user, movement, "update", changes={"status": "dispatched"}, tenant=request.tenant)

    messages.success(request, f"Asset {movement.asset.number} marked dispatched in movement {movement.number}.")
    return redirect("assets:asset_movement_log_detail", pk=movement.pk)


@login_required
@require_POST
def asset_movement_log_receive(request, pk):
    movement = get_object_or_404(AssetMovementLog.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    if movement.status not in ("dispatched", "in_transit"):
        messages.error(request, f"Cannot receive transfer in '{movement.get_status_display()}' state. Must be dispatched first.")
        return redirect("assets:asset_movement_log_detail", pk=movement.pk)

    condition = request.POST.get("condition_on_receipt", "good").strip()
    valid_conditions = dict(AssetMovementLog.CONDITION_CHOICES)
    if condition not in valid_conditions:
        condition = "good"

    with transaction.atomic():
        movement.status = "received"
        movement.received_date = timezone.now()
        movement.received_by = request.user
        movement.condition_on_receipt = condition
        movement.save(update_fields=["status", "received_date", "received_by", "condition_on_receipt", "updated_at"])

        # Update the operational asset's current location if to_location was specified
        if movement.to_location:
            movement.asset.location = movement.to_location
            movement.asset.save(update_fields=["location", "updated_at"])

        write_audit_log(request.user, movement, "update", changes={"status": "received", "condition": condition}, tenant=request.tenant)

    messages.success(request, f"Asset {movement.asset.number} received at {movement.to_location.name if movement.to_location else 'destination'}.")
    return redirect("assets:asset_movement_log_detail", pk=movement.pk)


@login_required
@require_POST
def asset_movement_log_cancel(request, pk):
    movement = get_object_or_404(AssetMovementLog, pk=pk, tenant=request.tenant)
    if movement.status in ("received", "cancelled"):
        messages.error(request, f"Cannot cancel movement in '{movement.get_status_display()}' state.")
        return redirect("assets:asset_movement_log_detail", pk=movement.pk)

    with transaction.atomic():
        movement.status = "cancelled"
        movement.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, movement, "update", changes={"status": "cancelled"}, tenant=request.tenant)

    messages.info(request, f"Movement {movement.number} cancelled.")
    return redirect("assets:asset_movement_log_detail", pk=movement.pk)
