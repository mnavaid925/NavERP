import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.quality.forms.EhsManagement.SafetyIncidents import SafetyIncidentForm
from apps.quality.models.EhsManagement.SafetyIncidents import SafetyIncident
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def safety_incident_list(request):
    qs = quality_scope(SafetyIncident.objects.all(), request).select_related(
        "org_unit", "reported_by", "affected_person"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(location_details__icontains=q)
            | Q(affected_party_name__icontains=q)
            | Q(investigation_findings__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("incident_type", "").strip()
    if type_filter:
        qs = qs.filter(incident_type=type_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    osha_filter = request.GET.get("is_osha_recordable", "").strip()
    if osha_filter in ("1", "true", "True"):
        qs = qs.filter(is_osha_recordable=True)
    elif osha_filter in ("0", "false", "False"):
        qs = qs.filter(is_osha_recordable=False)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    context = {
        "safety_incidents": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "status_choices": SafetyIncident.STATUS_CHOICES,
        "incident_type_choices": SafetyIncident.INCIDENT_TYPE_CHOICES,
        "severity_choices": SafetyIncident.SEVERITY_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/ehsmanagement/safety_incident/list.html", context)


@login_required
def safety_incident_create(request):
    if request.method == "POST":
        form = SafetyIncidentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Safety incident report {obj.number} logged successfully.")
            return redirect("quality:safety_incident_detail", pk=obj.pk)
    else:
        form = SafetyIncidentForm(
            tenant=request.tenant,
            initial={
                "incident_date": timezone.now(),
                "report_date": timezone.now().date(),
                "reported_by": request.user,
            },
        )

    context = {
        "form": form,
        "safety_incident": None,
        "is_edit": False,
    }
    return render(request, "quality/ehsmanagement/safety_incident/form.html", context)


@login_required
def safety_incident_detail(request, pk):
    obj = quality_object(
        request,
        SafetyIncident,
        pk,
        select_related=[
            "org_unit",
            "reported_by",
            "affected_person",
            "lead_investigator",
            "capa_investigation",
            "non_conformance_report",
        ],
    )
    context = {
        "safety_incident": obj,
    }
    return render(request, "quality/ehsmanagement/safety_incident/detail.html", context)


@login_required
def safety_incident_update(request, pk):
    obj = quality_object(
        request,
        SafetyIncident,
        pk,
        select_related=[
            "org_unit",
            "reported_by",
            "affected_person",
            "lead_investigator",
            "capa_investigation",
            "non_conformance_report",
        ],
    )
    if request.method == "POST":
        form = SafetyIncidentForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Safety incident report {obj.number} updated successfully.")
            return redirect("quality:safety_incident_detail", pk=obj.pk)
    else:
        form = SafetyIncidentForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "safety_incident": obj,
        "is_edit": True,
    }
    return render(request, "quality/ehsmanagement/safety_incident/form.html", context)


safety_incident_edit = safety_incident_update


@login_required
@require_POST
def safety_incident_delete(request, pk):
    obj = quality_object(request, SafetyIncident, pk)
    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.error(request, "Only tenant administrators can delete safety incident reports.")
        return redirect("quality:safety_incident_detail", pk=obj.pk)

    if obj.is_osha_recordable:
        messages.error(request, "Statutory OSHA 300 recordable incidents cannot be deleted.")
        return redirect("quality:safety_incident_detail", pk=obj.pk)

    num = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Safety incident report {num} deleted.")
    return redirect("quality:safety_incident_list")


@login_required
def safety_incident_export(request):
    qs = quality_scope(SafetyIncident.objects.all(), request).select_related(
        "org_unit", "reported_by", "affected_person", "lead_investigator"
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(location_details__icontains=q)
            | Q(affected_party_name__icontains=q)
            | Q(investigation_findings__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("incident_type", "").strip()
    if type_filter:
        qs = qs.filter(incident_type=type_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    osha_filter = request.GET.get("is_osha_recordable", "").strip()
    if osha_filter in ("1", "true", "True"):
        qs = qs.filter(is_osha_recordable=True)
    elif osha_filter in ("0", "false", "False"):
        qs = qs.filter(is_osha_recordable=False)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="safety_incidents_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Incident Number",
        "Title",
        "Date Occurred",
        "Report Date",
        "Type",
        "Severity",
        "Status",
        "Facility",
        "Affected Person",
        "Party Type",
        "Injury Nature",
        "Body Part",
        "OSHA Recordable",
        "OSHA Classification",
        "Lost Days",
        "Restricted Days",
        "Lead Investigator",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.incident_date),
            _csv_safe(item.report_date),
            _csv_safe(item.get_incident_type_display()),
            _csv_safe(item.get_severity_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.org_unit.name if item.org_unit else ""),
            _csv_safe(item.affected_person_display),
            _csv_safe(item.get_affected_party_type_display()),
            _csv_safe(item.get_nature_of_injury_display()),
            _csv_safe(item.get_body_part_affected_display()),
            _csv_safe("Yes" if item.is_osha_recordable else "No"),
            _csv_safe(item.get_osha_classification_display()),
            _csv_safe(item.lost_workdays_count),
            _csv_safe(item.restricted_workdays_count),
            _csv_safe(item.lead_investigator.get_full_name() or item.lead_investigator.username if item.lead_investigator else ""),
        ])
    return response


@login_required
@require_POST
def safety_incident_investigate(request, pk):
    obj = quality_object(request, SafetyIncident, pk)
    findings = request.POST.get("investigation_findings", "").strip()
    root_cause = request.POST.get("root_cause_category", "").strip()
    action = request.POST.get("investigation_action", "review").strip()

    if findings:
        obj.investigation_findings = findings
    if root_cause and root_cause in dict(SafetyIncident.ROOT_CAUSE_CATEGORY_CHOICES):
        obj.root_cause_category = root_cause

    if action == "close":
        obj.status = "closed"
    elif action == "capa":
        obj.status = "capa_pending"
    else:
        obj.status = "under_review"

    obj.save(update_fields=["investigation_findings", "root_cause_category", "status", "updated_at"])
    write_audit_log(
        request.user,
        obj,
        "update",
        changes={"action": "investigate", "status": obj.status},
        tenant=request.tenant,
    )
    messages.success(request, f"Investigation findings logged for {obj.number}. Status updated to {obj.get_status_display()}.")
    return redirect("quality:safety_incident_detail", pk=obj.pk)
