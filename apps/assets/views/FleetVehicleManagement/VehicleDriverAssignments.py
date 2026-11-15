"""Views for Vehicle Driver Assignments, qualifications and safety logs (11.19)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.FleetVehicleManagement.VehicleDriverAssignments import VehicleDriverAssignmentForm
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleDriverAssignments import VehicleDriverAssignment
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.FleetVehicleManagement._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile

_DRIVER_SELECT_RELATED = (
    "vehicle",
    "driver__party",
    "user",
)


def _filter_driver_assignments_queryset(request, base_qs):
    qs = base_qs.select_related(*_DRIVER_SELECT_RELATED)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(vehicle__name__icontains=q)
            | Q(vehicle__license_plate__icontains=q)
            | Q(driver_license_number__icontains=q)
            | Q(driver__party__name__icontains=q)
        )
    qs = apply_fk_filter(qs, request, "vehicle", "vehicle_id")
    qs = apply_fk_filter(qs, request, "driver", "driver_id")
    qs = apply_choice_filter(qs, request, "status", allowed_values=[c[0] for c in VehicleDriverAssignment.STATUS_CHOICES])
    qs = apply_choice_filter(qs, request, "safety_tier", allowed_values=[c[0] for c in VehicleDriverAssignment.SAFETY_TIER_CHOICES])
    return qs


@login_required
def vehicle_driver_assignment_list(request):
    """List vehicle driver assignments with safety scores and filters."""
    base_qs = assets_scope(VehicleDriverAssignment.objects, request)
    filtered_qs = _filter_driver_assignments_queryset(request, base_qs)

    aggregates = base_qs.aggregate(
        active_count=Count("id", filter=Q(status="active")),
        high_risk_count=Count("id", filter=Q(safety_tier="high_risk")),
    )

    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "assignments": page_obj,
        "page_obj": page_obj,
        "vehicles": FleetVehicle.objects.filter(tenant=request.tenant),
        "drivers": EmployeeProfile.objects.filter(tenant=request.tenant),
        "status_choices": VehicleDriverAssignment.STATUS_CHOICES,
        "safety_tier_choices": VehicleDriverAssignment.SAFETY_TIER_CHOICES,
        "active_count": aggregates["active_count"] or 0,
        "high_risk_count": aggregates["high_risk_count"] or 0,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_driver_assignment/list.html", context)


@login_required
def vehicle_driver_assignment_export(request):
    """Export filtered driver assignments to CSV."""
    base_qs = assets_scope(VehicleDriverAssignment.objects, request)
    filtered_qs = _filter_driver_assignments_queryset(request, base_qs)

    headers = [
        "Assignment Number",
        "Vehicle",
        "Driver",
        "Role",
        "Status",
        "Start Datetime",
        "End Datetime",
        "License Class",
        "Qualification Status",
        "Safety Score",
        "Safety Tier",
        "Incidents",
        "Duty Status",
    ]

    def generate_rows():
        for a in filtered_qs:
            yield [
                a.number,
                a.vehicle.name if a.vehicle else "",
                str(a.driver) if a.driver else "",
                a.get_assignment_role_display(),
                a.get_status_display(),
                a.start_datetime.strftime("%Y-%m-%d %H:%M"),
                a.end_datetime.strftime("%Y-%m-%d %H:%M") if a.end_datetime else "",
                a.get_license_class_display(),
                a.get_qualification_status_display(),
                a.safety_score,
                a.get_safety_tier_display(),
                a.incident_count,
                a.get_duty_status_display(),
            ]

    filename = f"driver_assignments_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return csv_export_response(filename, headers, generate_rows())


@login_required
def vehicle_driver_assignment_detail(request, pk):
    """Detail view for a driver assignment and safety record."""
    assignment = assets_object(request, VehicleDriverAssignment, pk, select_related=_DRIVER_SELECT_RELATED)
    return render(request, "assets/fleetvehiclemanagement/vehicle_driver_assignment/detail.html", {"assignment": assignment})


@login_required
def vehicle_driver_assignment_create(request):
    """Create a new driver assignment."""
    initial_data = {}
    vehicle_pk = request.GET.get("vehicle")
    if vehicle_pk and vehicle_pk.isdigit():
        initial_data["vehicle"] = vehicle_pk

    if request.method == "POST":
        form = VehicleDriverAssignmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.tenant = request.tenant
            assignment.save()
            form.save_m2m()
            write_audit_log(request.user, assignment, "create", tenant=request.tenant)
            messages.success(request, f"Driver assignment '{assignment.number}' created successfully.")
            return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)
    else:
        form = VehicleDriverAssignmentForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "assignment": None,
        "is_edit": False,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_driver_assignment/form.html", context)


@login_required
def vehicle_driver_assignment_edit(request, pk):
    """Edit an existing driver assignment."""
    assignment = assets_object(request, VehicleDriverAssignment, pk)
    if request.method == "POST":
        form = VehicleDriverAssignmentForm(request.POST, instance=assignment, tenant=request.tenant)
        if form.is_valid():
            assignment = form.save()
            write_audit_log(request.user, assignment, "update", tenant=request.tenant)
            messages.success(request, f"Driver assignment '{assignment.number}' updated successfully.")
            return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)
    else:
        form = VehicleDriverAssignmentForm(instance=assignment, tenant=request.tenant)

    context = {
        "form": form,
        "assignment": assignment,
        "is_edit": True,
    }
    return render(request, "assets/fleetvehiclemanagement/vehicle_driver_assignment/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def vehicle_driver_assignment_delete(request, pk):
    """Delete a driver assignment."""
    assignment = assets_object(request, VehicleDriverAssignment, pk)
    number = assignment.number
    write_audit_log(request.user, assignment, "delete", tenant=request.tenant)
    assignment.delete()
    messages.success(request, f"Driver assignment '{number}' deleted.")
    return redirect("assets:vehicle_driver_assignment_list")


@login_required
@require_POST
def vehicle_driver_assignment_complete(request, pk):
    """Mark a driver assignment completed / vehicle checked back in."""
    assignment = assets_object(request, VehicleDriverAssignment, pk)
    if assignment.status != "active":
        messages.error(request, f"Assignment '{assignment.number}' is not active and cannot be completed.")
        return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)

    assignment.status = "completed"
    if not assignment.end_datetime:
        assignment.end_datetime = timezone.now()
    assignment.save(update_fields=["status", "end_datetime", "updated_at"])
    write_audit_log(request.user, assignment, "complete", tenant=request.tenant)
    messages.success(request, f"Assignment '{assignment.number}' marked Completed.")
    return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)


@login_required
@require_POST
@tenant_admin_required
def vehicle_driver_assignment_revoke(request, pk):
    """Revoke driver assignment for safety violation."""
    assignment = assets_object(request, VehicleDriverAssignment, pk)
    if assignment.status != "active":
        messages.error(request, f"Assignment '{assignment.number}' is not active and cannot be revoked.")
        return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)

    assignment.status = "revoked_safety"
    assignment.qualification_status = "suspended"
    assignment.save(update_fields=["status", "qualification_status", "updated_at"])
    write_audit_log(request.user, assignment, "revoke", tenant=request.tenant)
    messages.error(request, f"Driver assignment '{assignment.number}' revoked for safety standing.")
    return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)


@login_required
@require_POST
def vehicle_driver_assignment_record_incident(request, pk):
    """Log safety incident and re-calculate score."""
    assignment = assets_object(request, VehicleDriverAssignment, pk)
    if assignment.status != "active":
        messages.error(request, f"Assignment '{assignment.number}' is not active. Incidents can only be recorded on active assignments.")
        return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)

    assignment.incident_count += 1
    assignment.safety_score = max(0, assignment.safety_score - 10)
    assignment.save()
    write_audit_log(request.user, assignment, "incident", tenant=request.tenant)
    messages.warning(request, f"Safety incident logged for '{assignment.driver}'. Safety score updated to {assignment.safety_score}.")
    return redirect("assets:vehicle_driver_assignment_detail", pk=assignment.pk)
