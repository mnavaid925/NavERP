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

    host_id = request.GET.get("host")
    selected_host = None
    if host_id and host_id.isdigit():
        selected_host = active_qs.filter(pk=int(host_id)).first()

    if not selected_host:
        selected_host = active_qs.filter(status__in=["active_inspection", "daily_wrapup"]).first() or active_qs.first()

    request_form = InspectionLogRequestForm(tenant=request.tenant) if selected_host else None
    fulfillment_rate = selected_host.fulfillment_rate if selected_host else 100

    context = {
        "active_inspections": active_qs,
        "selected_host": selected_host,
        "total_active_count": active_qs.filter(status__in=["active_inspection", "daily_wrapup"]).count(),
        "fulfillment_rate": fulfillment_rate,
        "request_form": request_form,
    }
    return render(request, "quality/auditmanagement/audit_war_room.html", context)
