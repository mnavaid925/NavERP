"""Views for Vehicle Fuel Log transactions and consumption tracking (11.19)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.FleetVehicleManagement.VehicleFuelLogs import VehicleFuelLogForm
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleFuelLogs import VehicleFuelLog
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.FleetVehicleManagement._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

_FUEL_SELECT_RELATED = (
    "vehicle",
    "driver__party",
    "fuel_vendor",
    "currency",
)


def _filter_fuel_queryset(request, base_qs):
    qs = base_qs.select_related(*_FUEL_SELECT_RELATED)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(vehicle__name__icontains=q)
            | Q(vehicle__license_plate__icontains=q)
            | Q(fuel_station_name__icontains=q)
            | Q(fuel_card_token__icontains=q)
        )
    qs = apply_fk_filter(qs, request, "vehicle", "vehicle_id")
    qs = apply_choice_filter(qs, request, "fuel_type", allowed_values=[c[0] for c in VehicleFuelLog.FUEL_TYPE_CHOICES])
    qs = apply_choice_filter(qs, request, "efficiency_rating", allowed_values=[c[0] for c in VehicleFuelLog.EFFICIENCY_RATING_CHOICES])
    return qs


@login_required
def vehicle_fuel_log_list(request):
    """List vehicle fuel fill-up logs with metrics and filters."""
    base_qs = assets_scope(VehicleFuelLog.objects, request)
    filtered_qs = _filter_fuel_queryset(request, base_qs)

    aggregates = base_qs.aggregate(
        total_cost_sum=Sum("total_cost"),
        total_gallons_sum=Sum("quantity_gallons"),
        avg_mpg=Avg("calculated_mpg"),
    )

    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "fuel_logs": page_obj,
        "page_obj": page_obj,
        "vehicles": FleetVehicle.objects.filter(tenant=request.tenant),
        "fuel_type_choices": VehicleFuelLog.FUEL_TYPE_CHOICES,
        "efficiency_choices": VehicleFuelLog.EFFICIENCY_RATING_CHOICES,
        "total_cost_sum": aggregates["total_cost_sum"] or 0,
        "total_spend": aggregates["total_cost_sum"] or 0,
        "total_gallons_sum": aggregates["total_gallons_sum"] or 0,
        "total_gallons": aggregates["total_gallons_sum"] or 0,
        "avg_mpg": round(aggregates["avg_mpg"], 1) if aggregates["avg_mpg"] else 0,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_fuel_log/list.html", context)


@login_required
def vehicle_fuel_log_export(request):
    """Export filtered fuel logs to CSV."""
    base_qs = assets_scope(VehicleFuelLog.objects, request)
    filtered_qs = _filter_fuel_queryset(request, base_qs)

    headers = [
        "Log Number",
        "Vehicle",
        "Date",
        "Odometer",
        "Fuel Type",
        "Quantity (Gal/kWh)",
        "Unit Price",
        "Total Cost",
        "Full Tank",
        "Distance Since Last",
        "Calculated MPG",
        "Efficiency",
        "Station",
        "Driver",
    ]

    def generate_rows():
        for f in filtered_qs:
            yield [
                f.number,
                f.vehicle.name if f.vehicle else "",
                f.fuel_date.strftime("%Y-%m-%d %H:%M"),
                f.odometer_at_fueling,
                f.get_fuel_type_display(),
                f.quantity_gallons,
                f.unit_price,
                f.total_cost,
                "Yes" if f.is_full_tank else "No",
                f.distance_since_last_fuel or "",
                f.calculated_mpg or "",
                f.get_efficiency_rating_display(),
                f.fuel_station_name,
                str(f.driver) if f.driver else "",
            ]

    filename = f"fuel_logs_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_export_response(filename, headers, generate_rows())


@login_required
def vehicle_fuel_log_detail(request, pk):
    """Detail view for a single fuel fill-up transaction."""
    fuel_log = assets_object(request, VehicleFuelLog, pk, select_related=_FUEL_SELECT_RELATED)
    return render(request, "assets/fleetvehiclemanagement/vehicle_fuel_log/detail.html", {"fuel_log": fuel_log})


@login_required
def vehicle_fuel_log_create(request):
    """Record a new vehicle fuel log."""
    initial_data = {}
    vehicle_pk = request.GET.get("vehicle")
    if vehicle_pk and vehicle_pk.isdigit():
        initial_data["vehicle"] = vehicle_pk

    if request.method == "POST":
        form = VehicleFuelLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            fuel_log = form.save(commit=False)
            fuel_log.tenant = request.tenant
            fuel_log.save()
            form.save_m2m()
            write_audit_log(request.user, fuel_log, "create", tenant=request.tenant)
            messages.success(request, f"Fuel log '{fuel_log.number}' recorded successfully.")
            return redirect("assets:vehicle_fuel_log_detail", pk=fuel_log.pk)
    else:
        form = VehicleFuelLogForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "fuel_log": None,
        "is_edit": False,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_fuel_log/form.html", context)


@login_required
def vehicle_fuel_log_edit(request, pk):
    """Edit an existing vehicle fuel log."""
    fuel_log = assets_object(request, VehicleFuelLog, pk)
    if request.method == "POST":
        form = VehicleFuelLogForm(request.POST, instance=fuel_log, tenant=request.tenant)
        if form.is_valid():
            fuel_log = form.save()
            write_audit_log(request.user, fuel_log, "update", tenant=request.tenant)
            messages.success(request, f"Fuel log '{fuel_log.number}' updated successfully.")
            return redirect("assets:vehicle_fuel_log_detail", pk=fuel_log.pk)
    else:
        form = VehicleFuelLogForm(instance=fuel_log, tenant=request.tenant)

    context = {
        "form": form,
        "fuel_log": fuel_log,
        "is_edit": True,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_fuel_log/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def vehicle_fuel_log_delete(request, pk):
    """Delete a vehicle fuel log."""
    fuel_log = assets_object(request, VehicleFuelLog, pk)
    number = fuel_log.number
    write_audit_log(request.user, fuel_log, "delete", tenant=request.tenant)
    fuel_log.delete()
    messages.success(request, f"Fuel log '{number}' deleted.")
    return redirect("assets:vehicle_fuel_log_list")
