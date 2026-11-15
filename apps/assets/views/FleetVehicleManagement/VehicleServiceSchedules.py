"""Views for Vehicle Service Schedules and Preventive Maintenance (11.19)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.FleetVehicleManagement.VehicleServiceSchedules import VehicleServiceScheduleForm
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleServiceSchedules import VehicleServiceSchedule
from apps.assets.views._common import assets_object, assets_scope, safe_parse_date
from apps.assets.views.FleetVehicleManagement._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

_SERVICE_SELECT_RELATED = (
    "vehicle",
    "service_vendor",
    "warranty",
    "maintenance_schedule",
    "currency",
)


def _filter_service_queryset(request, base_qs):
    qs = base_qs.select_related(*_SERVICE_SELECT_RELATED)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(service_title__icontains=q)
            | Q(vehicle__name__icontains=q)
            | Q(vehicle__license_plate__icontains=q)
            | Q(work_order_invoice_ref__icontains=q)
        )
    qs = apply_fk_filter(qs, request, "vehicle", "vehicle_id")
    qs = apply_choice_filter(qs, request, "service_type", allowed_values=[c[0] for c in VehicleServiceSchedule.SERVICE_TYPE_CHOICES])
    qs = apply_choice_filter(qs, request, "status", allowed_values=[c[0] for c in VehicleServiceSchedule.STATUS_CHOICES])
    qs = apply_choice_filter(qs, request, "priority", allowed_values=[c[0] for c in VehicleServiceSchedule.PRIORITY_CHOICES])
    return qs


@login_required
def vehicle_service_schedule_list(request):
    """List vehicle service schedules with filters and overdue alerts."""
    base_qs = assets_scope(VehicleServiceSchedule.objects, request)
    filtered_qs = _filter_service_queryset(request, base_qs)

    aggregates = base_qs.aggregate(
        overdue_count=Count("id", filter=Q(status="overdue")),
        due_soon_count=Count("id", filter=Q(status="due_soon")),
    )

    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "schedules": page_obj,
        "page_obj": page_obj,
        "vehicles": FleetVehicle.objects.filter(tenant=request.tenant),
        "service_type_choices": VehicleServiceSchedule.SERVICE_TYPE_CHOICES,
        "status_choices": VehicleServiceSchedule.STATUS_CHOICES,
        "priority_choices": VehicleServiceSchedule.PRIORITY_CHOICES,
        "overdue_count": aggregates["overdue_count"] or 0,
        "due_soon_count": aggregates["due_soon_count"] or 0,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_service_schedule/list.html", context)


@login_required
def vehicle_service_schedule_export(request):
    """Export filtered vehicle service schedules to CSV."""
    base_qs = assets_scope(VehicleServiceSchedule.objects, request)
    filtered_qs = _filter_service_queryset(request, base_qs)

    headers = [
        "Schedule #",
        "Vehicle",
        "Title",
        "Service Type",
        "Status",
        "Priority",
        "Next Due Date",
        "Next Due Odometer",
        "Interval (Months)",
        "Interval (Miles)",
        "Est. Cost",
        "Vendor",
    ]

    def generate_rows():
        for s in filtered_qs:
            yield [
                s.number,
                s.vehicle.name if s.vehicle else "",
                s.service_title,
                s.get_service_type_display(),
                s.get_status_display(),
                s.get_priority_display(),
                s.next_due_date or "",
                s.next_due_odometer or "",
                s.interval_months,
                s.interval_mileage,
                s.estimated_cost,
                str(s.service_vendor) if s.service_vendor else "",
            ]

    filename = f"vehicle_service_schedules_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_export_response(filename, headers, generate_rows())


@login_required
def vehicle_service_schedule_detail(request, pk):
    """Detail view for a vehicle service schedule."""
    schedule = assets_object(request, VehicleServiceSchedule, pk, select_related=_SERVICE_SELECT_RELATED)
    schedule.refresh_status()
    return render(request, "assets/fleetvehiclemanagement/vehicle_service_schedule/detail.html", {"schedule": schedule})


@login_required
def vehicle_service_schedule_create(request):
    """Create a new vehicle maintenance schedule."""
    initial_data = {}
    vehicle_pk = request.GET.get("vehicle")
    if vehicle_pk and vehicle_pk.isdigit():
        initial_data["vehicle"] = vehicle_pk

    if request.method == "POST":
        form = VehicleServiceScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.tenant = request.tenant
            schedule.refresh_status()
            schedule.save()
            form.save_m2m()
            write_audit_log(request.user, schedule, "create", tenant=request.tenant)
            messages.success(request, f"Service schedule '{schedule.service_title}' created successfully.")
            return redirect("assets:vehicle_service_schedule_detail", pk=schedule.pk)
    else:
        form = VehicleServiceScheduleForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "schedule": None,
        "is_edit": False,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_service_schedule/form.html", context)


@login_required
def vehicle_service_schedule_edit(request, pk):
    """Edit an existing vehicle maintenance schedule."""
    schedule = assets_object(request, VehicleServiceSchedule, pk)
    if request.method == "POST":
        form = VehicleServiceScheduleForm(request.POST, instance=schedule, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.refresh_status()
            schedule.save()
            form.save_m2m()
            write_audit_log(request.user, schedule, "update", tenant=request.tenant)
            messages.success(request, f"Service schedule '{schedule.service_title}' updated successfully.")
            return redirect("assets:vehicle_service_schedule_detail", pk=schedule.pk)
    else:
        form = VehicleServiceScheduleForm(instance=schedule, tenant=request.tenant)

    context = {
        "form": form,
        "schedule": schedule,
        "is_edit": True,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_service_schedule/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def vehicle_service_schedule_delete(request, pk):
    """Delete a vehicle service schedule."""
    schedule = assets_object(request, VehicleServiceSchedule, pk)
    number = schedule.number
    write_audit_log(request.user, schedule, "delete", tenant=request.tenant)
    schedule.delete()
    messages.success(request, f"Service schedule '{number}' deleted.")
    return redirect("assets:vehicle_service_schedule_list")


@login_required
@require_POST
@tenant_admin_required
def vehicle_service_schedule_complete(request, pk):
    """Complete a service event, log actual costs, and roll forward interval due dates."""
    schedule = assets_object(request, VehicleServiceSchedule, pk)
    comp_date_raw = request.POST.get("completion_date")
    completion_date = safe_parse_date(comp_date_raw) or timezone.now().date()

    odometer_raw = request.POST.get("odometer")
    try:
        odometer = int(odometer_raw) if odometer_raw and odometer_raw.strip().isdigit() else schedule.vehicle.current_odometer
        if odometer < 0 or odometer > 9999999:
            odometer = schedule.vehicle.current_odometer
    except (ValueError, TypeError):
        odometer = schedule.vehicle.current_odometer

    cost_raw = request.POST.get("actual_cost")
    try:
        cost = Decimal(cost_raw) if cost_raw else Decimal("0.00")
        if not cost.is_finite() or cost < Decimal("0.00") or cost > Decimal("9999999999.99"):
            cost = Decimal("0.00")
    except Exception:
        cost = Decimal("0.00")

    notes = request.POST.get("technician_notes", "").strip()

    schedule.complete_service(completion_date, odometer, cost=cost, notes=notes)
    write_audit_log(request.user, schedule, "complete", tenant=request.tenant)
    messages.success(request, f"Service '{schedule.service_title}' marked completed and rolled forward.")
    return redirect("assets:vehicle_service_schedule_detail", pk=schedule.pk)


@login_required
@require_POST
def vehicle_service_schedule_mark_in_service(request, pk):
    """Mark schedule in service at shop."""
    schedule = assets_object(request, VehicleServiceSchedule, pk)
    schedule.status = "in_service"
    schedule.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, schedule, "in_serv", tenant=request.tenant)
    messages.warning(request, f"Service '{schedule.number}' marked In Service / At Shop.")
    return redirect("assets:vehicle_service_schedule_detail", pk=schedule.pk)


@login_required
@require_POST
def vehicle_service_schedule_pause(request, pk):
    """Pause tracking on a service schedule."""
    schedule = assets_object(request, VehicleServiceSchedule, pk)
    schedule.status = "paused"
    schedule.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, schedule, "pause", tenant=request.tenant)
    messages.info(request, f"Service tracking paused for '{schedule.number}'.")
    return redirect("assets:vehicle_service_schedule_detail", pk=schedule.pk)
