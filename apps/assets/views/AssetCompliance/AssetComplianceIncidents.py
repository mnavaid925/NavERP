from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetCompliance.AssetComplianceIncidents import AssetComplianceIncidentForm
from apps.assets.models.AssetCompliance.AssetComplianceIncidents import AssetComplianceIncident
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log


@login_required
def asset_compliance_incident_list(request):
    qs = assets_scope(
        AssetComplianceIncident.objects.select_related(
            "asset",
            "permit",
            "audit",
            "enforcement_agency",
            "assigned_investigator",
        ).defer("root_cause_analysis", "corrective_action_plan"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(citation_reference__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
            | Q(enforcement_agency__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    type_filter = request.GET.get("incident_type", "").strip()
    if type_filter:
        qs = qs.filter(incident_type=type_filter)

    agency_id = request.GET.get("agency", "").strip()
    if agency_id and agency_id.isdigit():
        qs = qs.filter(enforcement_agency_id=int(agency_id))

    # Aggregate KPI counts and fine exposure
    base_all = AssetComplianceIncident.objects.filter(tenant=request.tenant)
    total_incidents = base_all.count()
    open_count = base_all.filter(
        status__in=["open", "under_investigation", "capa_in_progress"]
    ).count()
    critical_severity_count = base_all.filter(
        severity__in=["serious", "repeat", "willful", "imminent_danger"]
    ).count()

    fines_data = base_all.aggregate(
        total_assessed=Sum("fine_assessed"),
        total_paid=Sum("fine_paid"),
    )
    total_fines_assessed = fines_data["total_assessed"] or Decimal("0.00")
    total_fines_paid = fines_data["total_paid"] or Decimal("0.00")

    agency_list = Party.objects.filter(tenant=request.tenant).order_by("name")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_incident/list.html",
        {
            "incidents": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetComplianceIncident.STATUS_CHOICES,
            "severity_choices": AssetComplianceIncident.SEVERITY_CHOICES,
            "type_choices": AssetComplianceIncident.INCIDENT_TYPE_CHOICES,
            "agency_list": agency_list,
            "total_incidents": total_incidents,
            "open_count": open_count,
            "critical_severity_count": critical_severity_count,
            "total_fines_assessed": total_fines_assessed,
            "total_fines_paid": total_fines_paid,
        },
    )


@login_required
def asset_compliance_incident_detail(request, pk):
    incident = assets_object(
        request,
        AssetComplianceIncident,
        pk,
        select_related=[
            "asset",
            "permit",
            "audit",
            "enforcement_agency",
            "assigned_investigator",
        ],
    )
    return render(
        request,
        "assets/assetcompliance/asset_compliance_incident/detail.html",
        {
            "incident": incident,
        },
    )


@login_required
def asset_compliance_incident_create(request):
    if request.method == "POST":
        form = AssetComplianceIncidentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.tenant = request.tenant
            incident.save()
            write_audit_log(
                request.user,
                incident,
                "create",
                changes={"details": f"Reported compliance incident {incident.number} ({incident.title})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Compliance incident {incident.number} logged successfully.")
            return redirect("assets:asset_compliance_incident_detail", pk=incident.pk)
    else:
        initial = {}
        permit_arg = request.GET.get("permit", "").strip()
        if permit_arg and permit_arg.isdigit():
            initial["permit"] = int(permit_arg)
        audit_arg = request.GET.get("audit", "").strip()
        if audit_arg and audit_arg.isdigit():
            initial["audit"] = int(audit_arg)
        asset_arg = request.GET.get("asset", "").strip()
        if asset_arg and asset_arg.isdigit():
            initial["asset"] = int(asset_arg)
        form = AssetComplianceIncidentForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_incident/form.html",
        {
            "form": form,
            "incident": None,
            "is_edit": False,
        },
    )


@login_required
def asset_compliance_incident_edit(request, pk):
    incident = assets_object(request, AssetComplianceIncident, pk)
    if request.method == "POST":
        form = AssetComplianceIncidentForm(request.POST, instance=incident, tenant=request.tenant)
        if form.is_valid():
            incident = form.save()
            write_audit_log(
                request.user,
                incident,
                "update",
                changes={"details": f"Updated compliance incident {incident.number} ({incident.title})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Compliance incident {incident.number} updated successfully.")
            return redirect("assets:asset_compliance_incident_detail", pk=incident.pk)
    else:
        form = AssetComplianceIncidentForm(instance=incident, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_incident/form.html",
        {
            "form": form,
            "incident": incident,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def asset_compliance_incident_delete(request, pk):
    incident = assets_object(request, AssetComplianceIncident, pk)
    num = incident.number
    write_audit_log(
        request.user,
        incident,
        "delete",
        changes={"details": f"Deleted compliance incident {num}"},
        tenant=request.tenant,
    )
    incident.delete()
    messages.success(request, f"Compliance incident {num} was deleted.")
    return redirect("assets:asset_compliance_incident_list")


@login_required
@require_POST
def asset_compliance_incident_resolve(request, pk):
    incident = assets_object(request, AssetComplianceIncident, pk)
    if incident.status in ["open", "under_investigation", "capa_in_progress", "under_agency_review", "appealed"]:
        incident.status = "resolved"
        incident.actual_resolution_date = timezone.now().date()
        incident.save(update_fields=["status", "actual_resolution_date", "updated_at"])
        write_audit_log(
            request.user,
            incident,
            "update",
            changes={"details": f"Resolved compliance incident {incident.number} with CAPA verification"},
            tenant=request.tenant,
        )
        messages.success(request, f"Incident {incident.number} is marked as Resolved.")
    else:
        messages.warning(request, f"Incident {incident.number} cannot be marked as resolved from status '{incident.get_status_display()}'.")
    return redirect("assets:asset_compliance_incident_detail", pk=incident.pk)


@login_required
@require_POST
def asset_compliance_incident_close(request, pk):
    incident = assets_object(request, AssetComplianceIncident, pk)
    if incident.status in ["resolved", "under_agency_review"]:
        incident.status = "closed"
        incident.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            incident,
            "update",
            changes={"details": f"Closed compliance incident {incident.number}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Incident {incident.number} is now Closed.")
    else:
        messages.warning(request, f"Incident {incident.number} must be resolved before closing.")
    return redirect("assets:asset_compliance_incident_detail", pk=incident.pk)
