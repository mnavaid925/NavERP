"""Views for Fleet Vehicle registry, DMV compliance and lifecycle management (11.19)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.FleetVehicleManagement.FleetVehicles import FleetVehicleForm
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.FleetVehicleManagement._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.AuditLog import AuditLog
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log

_VEHICLE_SELECT_RELATED = (
    "org_unit",
    "primary_driver__party",
    "custodian_party",
    "operational_asset",
    "fixed_asset",
    "asset_category",
    "asset_model",
)


def _filter_vehicles_queryset(request, base_qs):
    qs = base_qs.select_related(*_VEHICLE_SELECT_RELATED)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(license_plate__icontains=q)
            | Q(vin__icontains=q)
            | Q(make__icontains=q)
            | Q(model__icontains=q)
        )
    qs = apply_choice_filter(qs, request, "status", allowed_values=[c[0] for c in FleetVehicle.STATUS_CHOICES])
    qs = apply_choice_filter(qs, request, "vehicle_type", allowed_values=[c[0] for c in FleetVehicle.VEHICLE_TYPE_CHOICES])
    qs = apply_choice_filter(qs, request, "fuel_type", allowed_values=[c[0] for c in FleetVehicle.FUEL_TYPE_CHOICES])
    qs = apply_choice_filter(qs, request, "compliance_status", allowed_values=[c[0] for c in FleetVehicle.COMPLIANCE_STATUS_CHOICES])
    qs = apply_fk_filter(qs, request, "org_unit", "org_unit_id")
    return qs


@login_required
def fleet_vehicle_list(request):
    """List fleet vehicles with filters, KPI tiles, and pagination."""
    base_qs = assets_scope(FleetVehicle.objects, request)
    filtered_qs = _filter_vehicles_queryset(request, base_qs)

    aggregates = base_qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active_in_service")),
        in_shop_count=Count("id", filter=Q(status="in_shop_maintenance")),
        expired_compliance_count=Count("id", filter=Q(compliance_status="expired_non_compliant")),
    )

    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "vehicles": page_obj,
        "page_obj": page_obj,
        "status_choices": FleetVehicle.STATUS_CHOICES,
        "vehicle_type_choices": FleetVehicle.VEHICLE_TYPE_CHOICES,
        "fuel_type_choices": FleetVehicle.FUEL_TYPE_CHOICES,
        "compliance_choices": FleetVehicle.COMPLIANCE_STATUS_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant),
        "total_count": aggregates["total_count"] or 0,
        "active_count": aggregates["active_count"] or 0,
        "in_shop_count": aggregates["in_shop_count"] or 0,
        "expired_compliance_count": aggregates["expired_compliance_count"] or 0,
    }
    return render(request, "assets/fleetvehiclemanagement/fleet_vehicle/list.html", context)


@login_required
def fleet_vehicle_export(request):
    """Export filtered fleet vehicles to CSV with formula sanitization."""
    base_qs = assets_scope(FleetVehicle.objects, request)
    filtered_qs = _filter_vehicles_queryset(request, base_qs)

    headers = [
        "Vehicle Number",
        "Name",
        "License Plate",
        "VIN",
        "Make",
        "Model",
        "Year",
        "Vehicle Type",
        "Fuel Type",
        "Status",
        "Compliance Status",
        "Odometer",
        "Registration Expiry",
        "Department",
        "Primary Driver",
    ]

    def generate_rows():
        for v in filtered_qs:
            yield [
                v.number,
                v.name,
                v.license_plate,
                v.vin,
                v.make,
                v.model,
                v.year,
                v.get_vehicle_type_display(),
                v.get_fuel_type_display(),
                v.get_status_display(),
                v.get_compliance_status_display(),
                v.current_odometer,
                v.registration_expiration_date or "",
                str(v.org_unit) if v.org_unit else "",
                str(v.primary_driver) if v.primary_driver else "",
            ]

    filename = f"fleet_vehicles_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_export_response(filename, headers, generate_rows())


@login_required
def fleet_vehicle_detail(request, pk):
    """Vehicle detail page showing telemetry, fuel logs, driver assignments and service records."""
    vehicle = assets_object(request, FleetVehicle, pk, select_related=_VEHICLE_SELECT_RELATED)
    vehicle.refresh_compliance_status()

    fuel_logs = vehicle.fuel_logs.select_related("currency", "driver__party").order_by("-fuel_date")[:10]
    assignments = vehicle.driver_assignments.select_related("driver__party", "user").order_by("-start_datetime")[:10]
    service_schedules = vehicle.service_schedules.select_related("service_vendor", "currency").order_by("-created_at")[:10]
    vehicle_ct = ContentType.objects.get_for_model(FleetVehicle)
    recent_audits = AuditLog.objects.filter(
        tenant=request.tenant, content_type=vehicle_ct, object_id=vehicle.pk
    ).order_by("-at")[:10]

    context = {
        "vehicle": vehicle,
        "fuel_logs": fuel_logs,
        "assignments": assignments,
        "service_schedules": service_schedules,
        "recent_audits": recent_audits,
    }
    return render(request, "assets/fleetvehiclemanagement/fleet_vehicle/detail.html", context)


@login_required
def fleet_vehicle_create(request):
    """Create a new fleet vehicle."""
    if request.method == "POST":
        form = FleetVehicleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.tenant = request.tenant
            vehicle.refresh_compliance_status()
            vehicle.save()
            form.save_m2m()
            write_audit_log(request.user, vehicle, "create", tenant=request.tenant)
            messages.success(request, f"Fleet vehicle '{vehicle.name}' ({vehicle.number}) created successfully.")
            return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
    else:
        form = FleetVehicleForm(tenant=request.tenant)

    context = {
        "form": form,
        "vehicle": None,
        "is_edit": False,
    }
    return render(request, "assets/fleetvehiclemanagement/fleet_vehicle/form.html", context)


@login_required
def fleet_vehicle_edit(request, pk):
    """Edit an existing fleet vehicle."""
    vehicle = assets_object(request, FleetVehicle, pk)
    if vehicle.is_locked:
        messages.error(request, f"Vehicle '{vehicle.number}' is decommissioned and cannot be edited.")
        return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)

    if request.method == "POST":
        form = FleetVehicleForm(request.POST, instance=vehicle, tenant=request.tenant)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.refresh_compliance_status()
            vehicle.save()
            form.save_m2m()
            write_audit_log(request.user, vehicle, "update", tenant=request.tenant)
            messages.success(request, f"Fleet vehicle '{vehicle.name}' updated successfully.")
            return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
    else:
        form = FleetVehicleForm(instance=vehicle, tenant=request.tenant)

    context = {
        "form": form,
        "vehicle": vehicle,
        "is_edit": True,
    }
    return render(request, "assets/fleetvehiclemanagement/fleet_vehicle/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def fleet_vehicle_delete(request, pk):
    """Delete a fleet vehicle."""
    vehicle = assets_object(request, FleetVehicle, pk)
    number = vehicle.number
    name = vehicle.name
    write_audit_log(request.user, vehicle, "delete", tenant=request.tenant)
    vehicle.delete()
    messages.success(request, f"Fleet vehicle '{name}' ({number}) deleted.")
    return redirect("assets:fleet_vehicle_list")


@login_required
@require_POST
def fleet_vehicle_activate(request, pk):
    """Mark vehicle active in service."""
    vehicle = assets_object(request, FleetVehicle, pk)
    if vehicle.is_locked:
        messages.error(request, "Decommissioned vehicles cannot be activated.")
        return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
    vehicle.status = "active_in_service"
    vehicle.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, vehicle, "activate", tenant=request.tenant)
    messages.success(request, f"Vehicle '{vehicle.number}' marked Active in Service.")
    return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)


@login_required
@require_POST
def fleet_vehicle_mark_in_shop(request, pk):
    """Mark vehicle in shop for maintenance."""
    vehicle = assets_object(request, FleetVehicle, pk)
    if vehicle.is_locked:
        messages.error(request, "Decommissioned vehicles cannot be placed in shop.")
        return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
    vehicle.status = "in_shop_maintenance"
    vehicle.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, vehicle, "in_shop", tenant=request.tenant)
    messages.warning(request, f"Vehicle '{vehicle.number}' marked In Shop / Maintenance.")
    return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)


@login_required
@require_POST
def fleet_vehicle_mark_loaner(request, pk):
    """Mark vehicle out as loaner/temporary assignment."""
    vehicle = assets_object(request, FleetVehicle, pk)
    if vehicle.is_locked:
        messages.error(request, "Decommissioned vehicles cannot be loaned.")
        return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
    vehicle.status = "loaner_out"
    vehicle.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, vehicle, "loaner", tenant=request.tenant)
    messages.info(request, f"Vehicle '{vehicle.number}' marked Loaner Out.")
    return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)


@login_required
@require_POST
def fleet_vehicle_mark_out_of_service(request, pk):
    """Mark vehicle out of service."""
    vehicle = assets_object(request, FleetVehicle, pk)
    if vehicle.is_locked:
        messages.error(request, "Decommissioned vehicles cannot change state.")
        return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
    vehicle.status = "out_of_service"
    vehicle.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, vehicle, "out_serv", tenant=request.tenant)
    messages.error(request, f"Vehicle '{vehicle.number}' taken Out of Service.")
    return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)


@login_required
@require_POST
@tenant_admin_required
def fleet_vehicle_decommission(request, pk):
    """Decommission and retire a fleet vehicle."""
    vehicle = assets_object(request, FleetVehicle, pk)
    vehicle.status = "decommissioned"
    vehicle.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, vehicle, "decomm", tenant=request.tenant)
    messages.info(request, f"Vehicle '{vehicle.number}' decommissioned.")
    return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)


@login_required
@require_POST
def fleet_vehicle_ping_telemetry(request, pk):
    """Simulate or record a telematics ping update."""
    vehicle = assets_object(request, FleetVehicle, pk)
    if vehicle.is_locked:
        messages.error(request, f"Vehicle '{vehicle.number}' is decommissioned / locked and cannot receive telematics updates.")
        return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)

    vehicle.last_telemetry_at = timezone.now()
    vehicle.is_telematics_enabled = True
    vehicle.save(update_fields=["last_telemetry_at", "is_telematics_enabled", "updated_at"])
    write_audit_log(request.user, vehicle, "ping_gps", tenant=request.tenant)
    messages.success(request, f"Telematics heartbeat logged for '{vehicle.number}'.")
    return redirect("assets:fleet_vehicle_detail", pk=vehicle.pk)
