from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetInventoryTracking.AssetIncidentReports import AssetIncidentReportForm
from apps.assets.models.AssetInventoryTracking.AssetIncidentReports import AssetIncidentReport
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.scm.models import Asset, Location


@login_required
def asset_incident_report_list(request):
    qs = AssetIncidentReport.objects.filter(tenant=request.tenant).select_related(
        "asset", "last_known_location", "reported_by", "custodian_at_loss", "investigator", "write_off_authorized_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset__number__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(police_report_number__icontains=q)
            | Q(insurance_claim_number__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    incident_type = request.GET.get("incident_type", "").strip()
    if incident_type:
        qs = qs.filter(incident_type=incident_type)

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    asset_id = request.GET.get("asset", "").strip()
    if asset_id and asset_id.isdigit():
        qs = qs.filter(asset_id=int(asset_id))

    location_id = request.GET.get("location", "").strip()
    if location_id and location_id.isdigit():
        qs = qs.filter(last_known_location_id=int(location_id))

    all_tenant_incidents = AssetIncidentReport.objects.filter(tenant=request.tenant)
    counts = all_tenant_incidents.aggregate(
        total=Count("id"),
        reported=Count("id", filter=Q(status="reported")),
        investigating=Count("id", filter=Q(status="under_investigation")),
        confirmed_lost=Count("id", filter=Q(status="confirmed_lost")),
        write_off_pending=Count("id", filter=Q(status="write_off_pending")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    locations = Location.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    assets = Asset.objects.filter(tenant=request.tenant).order_by("number")

    context = {
        "incidents": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "locations": locations,
        "assets": assets,
        "type_choices": AssetIncidentReport.INCIDENT_TYPE_CHOICES,
        "severity_choices": AssetIncidentReport.SEVERITY_CHOICES,
        "status_choices": AssetIncidentReport.STATUS_CHOICES,
        "resolution_choices": AssetIncidentReport.RESOLUTION_ACTION_CHOICES,
        "q": q,
        "total_count": counts["total"] or 0,
        "reported_count": counts["reported"] or 0,
        "investigating_count": counts["investigating"] or 0,
        "confirmed_lost_count": counts["confirmed_lost"] or 0,
        "write_off_pending_count": counts["write_off_pending"] or 0,
    }
    return render(request, "assets/asset_inventory_tracking/asset_incident_report/list.html", context)


@login_required
def asset_incident_report_detail(request, pk):
    incident = get_object_or_404(
        AssetIncidentReport.objects.select_related(
            "asset", "last_known_location", "reported_by", "custodian_at_loss", "investigator", "write_off_authorized_by"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "assets/asset_inventory_tracking/asset_incident_report/detail.html",
        {"incident": incident},
    )


@login_required
def asset_incident_report_create(request):
    if request.method == "POST":
        form = AssetIncidentReportForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                if not obj.reported_by:
                    obj.reported_by = request.user
                obj.save()
                form.save_m2m()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Asset incident report {obj.number} created successfully.")
            return redirect("assets:asset_incident_report_detail", pk=obj.pk)
    else:
        initial = {}
        asset_id = request.GET.get("asset", "").strip()
        if asset_id and asset_id.isdigit():
            initial["asset"] = int(asset_id)
        form = AssetIncidentReportForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_incident_report/form.html",
        {"form": form, "incident": None, "is_edit": False},
    )


@login_required
def asset_incident_report_edit(request, pk):
    incident = get_object_or_404(AssetIncidentReport, pk=pk, tenant=request.tenant)
    if incident.status in ("written_off", "closed"):
        messages.error(request, f"Incident {incident.number} is {incident.get_status_display()} and cannot be edited.")
        return redirect("assets:asset_incident_report_detail", pk=incident.pk)

    if request.method == "POST":
        form = AssetIncidentReportForm(request.POST, instance=incident, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Asset incident report {obj.number} updated successfully.")
            return redirect("assets:asset_incident_report_detail", pk=obj.pk)
    else:
        form = AssetIncidentReportForm(instance=incident, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_incident_report/form.html",
        {"form": form, "incident": incident, "is_edit": True},
    )


@login_required
@require_POST
def asset_incident_report_delete(request, pk):
    incident = get_object_or_404(AssetIncidentReport, pk=pk, tenant=request.tenant)
    if incident.status not in ("reported", "closed"):
        messages.error(request, f"Cannot delete incident in '{incident.get_status_display()}' status.")
        return redirect("assets:asset_incident_report_detail", pk=incident.pk)

    num = incident.number
    with transaction.atomic():
        write_audit_log(request.user, incident, "delete", tenant=request.tenant)
        incident.delete()
    messages.success(request, f"Incident report {num} deleted.")
    return redirect("assets:asset_incident_report_list")


@login_required
@require_POST
def asset_incident_report_investigate(request, pk):
    incident = get_object_or_404(AssetIncidentReport, pk=pk, tenant=request.tenant)
    if incident.status not in ("reported", "confirmed_lost"):
        messages.error(request, f"Cannot place incident in '{incident.get_status_display()}' under investigation.")
        return redirect("assets:asset_incident_report_detail", pk=incident.pk)

    with transaction.atomic():
        incident.status = "under_investigation"
        if not incident.investigator:
            incident.investigator = request.user
        incident.save(update_fields=["status", "investigator", "updated_at"])
        write_audit_log(request.user, incident, "update", changes={"status": "under_investigation"}, tenant=request.tenant)

    messages.success(request, f"Incident {incident.number} placed under active investigation.")
    return redirect("assets:asset_incident_report_detail", pk=incident.pk)


@login_required
@require_POST
def asset_incident_report_resolve_recovered(request, pk):
    incident = get_object_or_404(AssetIncidentReport, pk=pk, tenant=request.tenant)
    if incident.status in ("written_off", "closed"):
        messages.error(request, f"Cannot recover asset from '{incident.get_status_display()}' incident.")
        return redirect("assets:asset_incident_report_detail", pk=incident.pk)

    notes = request.POST.get("investigation_findings", incident.investigation_findings).strip()

    with transaction.atomic():
        incident.status = "recovered"
        incident.resolution_action = "recovered"
        incident.investigation_findings = notes
        incident.save(update_fields=["status", "resolution_action", "investigation_findings", "updated_at"])
        write_audit_log(request.user, incident, "update", changes={"status": "recovered"}, tenant=request.tenant)

    messages.success(request, f"Asset {incident.asset.number} marked recovered. Incident resolved.")
    return redirect("assets:asset_incident_report_detail", pk=incident.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_incident_report_authorize_write_off(request, pk):
    incident = get_object_or_404(AssetIncidentReport.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    if incident.status in ("written_off", "closed"):
        messages.error(request, f"Incident {incident.number} is already {incident.get_status_display()}.")
        return redirect("assets:asset_incident_report_detail", pk=incident.pk)

    notes = request.POST.get("write_off_notes", incident.write_off_notes).strip()

    with transaction.atomic():
        incident.status = "written_off"
        incident.resolution_action = "written_off"
        incident.write_off_authorized_by = request.user
        incident.write_off_date = timezone.now().date()
        incident.write_off_notes = notes
        incident.save(
            update_fields=[
                "status",
                "resolution_action",
                "write_off_authorized_by",
                "write_off_date",
                "write_off_notes",
                "updated_at",
            ]
        )

        # Update the operational asset status to disposed/retired
        incident.asset.status = "disposed"
        incident.asset.save(update_fields=["status", "updated_at"])

        write_audit_log(
            request.user,
            incident,
            "update",
            changes={"status": "written_off", "asset_status": "disposed"},
            tenant=request.tenant,
        )

    messages.success(request, f"Write-off authorized for asset {incident.asset.number}. Asset decommissioned.")
    return redirect("assets:asset_incident_report_detail", pk=incident.pk)


@login_required
@require_POST
def asset_incident_report_close(request, pk):
    incident = get_object_or_404(AssetIncidentReport, pk=pk, tenant=request.tenant)
    if incident.status in ("closed", "written_off"):
        messages.error(request, f"Incident {incident.number} is already closed.")
        return redirect("assets:asset_incident_report_detail", pk=incident.pk)

    with transaction.atomic():
        incident.status = "closed"
        if incident.resolution_action == "pending":
            incident.resolution_action = "unresolved_closed"
        incident.save(update_fields=["status", "resolution_action", "updated_at"])
        write_audit_log(request.user, incident, "update", changes={"status": "closed"}, tenant=request.tenant)

    messages.info(request, f"Incident {incident.number} closed.")
    return redirect("assets:asset_incident_report_detail", pk=incident.pk)
