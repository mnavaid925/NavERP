from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.quality.forms.AuditManagement.RegulatoryInspectionHosts import InspectionLogRequestForm
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import RegulatoryInspectionHost
from apps.quality.views._common import quality_scope


@login_required
def audit_war_room(request):
    active_qs = quality_scope(
        RegulatoryInspectionHost.objects.select_related(
            "audit", "front_room_lead", "back_room_lead", "scribe_user"
        ),
        request,
    ).order_by("-scheduled_start_date")

    active_inspections = list(active_qs)

    host_id = request.GET.get("host")
    selected_host = None
    if host_id and host_id.isdigit():
        target_id = int(host_id)
        selected_host = next((h for h in active_inspections if h.pk == target_id), None)

    if not selected_host:
        selected_host = next((h for h in active_inspections if h.status in ("active_inspection", "daily_wrapup")), None)
        if not selected_host and active_inspections:
            selected_host = active_inspections[0]

    request_form = InspectionLogRequestForm(tenant=request.tenant) if selected_host else None
    fulfillment_rate = selected_host.fulfillment_rate if selected_host else 100

    context = {
        "active_inspections": active_inspections,
        "selected_host": selected_host,
        "fulfillment_rate": fulfillment_rate,
        "request_form": request_form,
    }
    return render(request, "quality/auditmanagement/audit_war_room.html", context)
