import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.quality.forms.AuditManagement.RegulatoryInspectionHosts import (
    InspectionLogRequestForm,
    RegulatoryInspectionHostForm,
)
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import RegulatoryInspectionHost
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log


@login_required
def regulatory_inspection_host_list(request):
    qs = quality_scope(
        RegulatoryInspectionHost.objects.select_related("audit", "front_room_lead", "back_room_lead", "scribe_user"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(inspection_title__icontains=q)
            | Q(number__icontains=q)
            | Q(agency_name__icontains=q)
            | Q(lead_inspector_name__icontains=q)
            | Q(war_room_location__icontains=q)
        )

    agency = request.GET.get("agency", "").strip()
    if agency:
        qs = qs.filter(agency_or_body=agency)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    formal_outcome = request.GET.get("formal_outcome", "").strip()
    if formal_outcome:
        qs = qs.filter(formal_outcome=formal_outcome)

    host_stats = RegulatoryInspectionHost.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status__in=["active_inspection", "daily_wrapup"])),
        form_483_count=Count("id", filter=Q(form_483_issued=True)),
    )
    total_count = host_stats["total_count"]
    active_count = host_stats["active_count"]
    form_483_count = host_stats["form_483_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "regulatory_inspection_hosts": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "form_483_count": form_483_count,
        "agency_choices": RegulatoryInspectionHost.AGENCY_CHOICES,
        "purpose_choices": RegulatoryInspectionHost.PURPOSE_CHOICES,
        "status_choices": RegulatoryInspectionHost.STATUS_CHOICES,
        "outcome_choices": RegulatoryInspectionHost.OUTCOME_CHOICES,
        "selected_agency": agency,
        "selected_status": status,
        "selected_outcome": formal_outcome,
        "search_query": q,
    }
    return render(request, "quality/auditmanagement/regulatory_inspection_host/list.html", context)


@login_required
def regulatory_inspection_host_detail(request, pk):
    host = quality_object(
        request,
        RegulatoryInspectionHost,
        pk,
        select_related=("audit", "front_room_lead", "back_room_lead", "scribe_user"),
    )
    request_form = InspectionLogRequestForm(tenant=request.tenant)

    context = {
        "regulatory_inspection_host": host,
        "obj": host,
        "request_form": request_form,
        "fulfillment_rate": host.fulfillment_rate,
        "pending_requests_count": host.pending_requests_count,
    }
    return render(request, "quality/auditmanagement/regulatory_inspection_host/detail.html", context)


@login_required
def regulatory_inspection_host_create(request):
    initial = {
        "scheduled_start_date": date.today(),
        "scheduled_end_date": date.today(),
        "front_room_lead": request.user.pk,
        "back_room_lead": request.user.pk,
    }
    audit_param = request.GET.get("audit", "").strip()
    if audit_param.isdigit():
        initial["audit"] = int(audit_param)

    if request.method == "POST":
        form = RegulatoryInspectionHostForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            host = form.save(commit=False)
            host.tenant = request.tenant
            host.save()
            write_audit_log(request.user, host, "create", tenant=request.tenant)
            messages.success(request, f"Regulatory Inspection Host Record {host.number} initialized.")
            return redirect("quality:regulatory_inspection_host_detail", pk=host.pk)
    else:
        form = RegulatoryInspectionHostForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "is_edit": False,
        "regulatory_inspection_host": None,
        "obj": None,
    }
    return render(request, "quality/auditmanagement/regulatory_inspection_host/form.html", context)


@login_required
def regulatory_inspection_host_edit(request, pk):
    host = quality_object(request, RegulatoryInspectionHost, pk)
    if request.method == "POST":
        form = RegulatoryInspectionHostForm(request.POST, instance=host, tenant=request.tenant)
        if form.is_valid():
            host = form.save()
            write_audit_log(request.user, host, "update", tenant=request.tenant)
            messages.success(request, f"Regulatory Inspection Record {host.number} updated successfully.")
            return redirect("quality:regulatory_inspection_host_detail", pk=host.pk)
    else:
        form = RegulatoryInspectionHostForm(instance=host, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "regulatory_inspection_host": host,
        "obj": host,
    }
    return render(request, "quality/auditmanagement/regulatory_inspection_host/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def regulatory_inspection_host_delete(request, pk):
    host = quality_object(request, RegulatoryInspectionHost, pk)
    number = host.number
    write_audit_log(request.user, host, "delete", tenant=request.tenant)
    host.delete()
    messages.success(request, f"Regulatory Inspection Record {number} deleted successfully.")
    return redirect("quality:regulatory_inspection_host_list")


@login_required
@require_POST
def regulatory_inspection_host_log_request(request, pk):
    host = quality_object(request, RegulatoryInspectionHost, pk)
    form = InspectionLogRequestForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        desc = form.cleaned_data["request_description"].strip()
        sme = form.cleaned_data.get("assigned_sme")
        priority = form.cleaned_data.get("priority")

        host.requests_logged_count += 1
        timestamp_str = timezone.now().strftime("%Y-%m-%d %H:%M")
        sme_name = sme.get_full_name() or sme.username if sme else "Unassigned"
        new_entry = f"[{timestamp_str}] [REQ #{host.requests_logged_count}] ({priority.upper()}) {desc} (Assigned: {sme_name})\n"
        host.daily_summary_notes = (host.daily_summary_notes or "") + new_entry
        host.save(update_fields=["requests_logged_count", "daily_summary_notes", "updated_at"])
        write_audit_log(request.user, host, "request", tenant=request.tenant)
        messages.success(request, f"Inspector document request #{host.requests_logged_count} logged in War Room.")
    else:
        messages.error(request, "Please enter a valid request description.")
    referer = request.META.get("HTTP_REFERER", "")
    if request.POST.get("source") == "war_room" or "war-room" in referer or "audit_war_room" in referer or "war_room" in referer:
        return redirect(f"{reverse('quality:audit_war_room')}?host={host.pk}")
    return redirect("quality:regulatory_inspection_host_detail", pk=host.pk)


@login_required
@require_POST
def regulatory_inspection_host_fulfill_request(request, pk):
    host = quality_object(request, RegulatoryInspectionHost, pk)
    if host.requests_fulfilled_count < host.requests_logged_count:
        host.requests_fulfilled_count += 1
        timestamp_str = timezone.now().strftime("%Y-%m-%d %H:%M")
        host.daily_summary_notes = (host.daily_summary_notes or "") + f"[{timestamp_str}] [FULFILLED] Request marked delivered to Front Room by {request.user.username}.\n"
        host.save(update_fields=["requests_fulfilled_count", "daily_summary_notes", "updated_at"])
        write_audit_log(request.user, host, "fulfill", tenant=request.tenant)
        messages.success(request, f"Request fulfilled ({host.requests_fulfilled_count}/{host.requests_logged_count}).")
    else:
        messages.info(request, "All logged inspector requests are already fulfilled.")
    referer = request.META.get("HTTP_REFERER", "")
    if request.POST.get("source") == "war_room" or "war-room" in referer or "audit_war_room" in referer or "war_room" in referer:
        return redirect(f"{reverse('quality:audit_war_room')}?host={host.pk}")
    return redirect("quality:regulatory_inspection_host_detail", pk=host.pk)


@login_required
@require_POST
def regulatory_inspection_host_close(request, pk):
    host = quality_object(request, RegulatoryInspectionHost, pk)
    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "role", "") == "admin"
    is_lead = (request.user.id in (host.front_room_lead_id, host.back_room_lead_id))
    if not (is_lead or is_admin):
        messages.error(request, "Only the Front Room Lead, Back Room Lead, or a tenant administrator can close this regulatory inspection record.")
        return redirect("quality:regulatory_inspection_host_detail", pk=host.pk)

    host.status = "inspection_closed"
    if not host.actual_end_date:
        host.actual_end_date = timezone.now().date()
    host.save(update_fields=["status", "actual_end_date", "updated_at"])
    write_audit_log(request.user, host, "close", tenant=request.tenant)
    messages.success(request, f"Inspection {host.number} officially marked closed.")
    return redirect("quality:regulatory_inspection_host_detail", pk=host.pk)


@login_required
def regulatory_inspection_host_export_csv(request):
    qs = quality_scope(
        RegulatoryInspectionHost.objects.select_related("audit", "front_room_lead", "back_room_lead"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(inspection_title__icontains=q) | Q(number__icontains=q) | Q(agency_name__icontains=q))

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="regulatory_inspections.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Host Number",
        "Inspection Title",
        "Agency",
        "Agency Name",
        "Lead Inspector",
        "Purpose",
        "Scheduled Start",
        "Scheduled End",
        "Front Room Lead",
        "Back Room Lead",
        "Requests Logged",
        "Requests Fulfilled",
        "Form 483 Issued",
        "Observations Count",
        "Outcome",
        "Status",
    ])

    for host in qs:
        writer.writerow([
            _csv_safe(host.number),
            _csv_safe(host.inspection_title),
            _csv_safe(host.get_agency_or_body_display()),
            _csv_safe(host.agency_name),
            _csv_safe(host.lead_inspector_name),
            _csv_safe(host.get_inspection_purpose_display()),
            _csv_safe(host.scheduled_start_date),
            _csv_safe(host.scheduled_end_date),
            _csv_safe(host.front_room_lead.get_full_name() or host.front_room_lead.username if host.front_room_lead else ""),
            _csv_safe(host.back_room_lead.get_full_name() or host.back_room_lead.username if host.back_room_lead else ""),
            _csv_safe(host.requests_logged_count),
            _csv_safe(host.requests_fulfilled_count),
            _csv_safe("Yes" if host.form_483_issued else "No"),
            _csv_safe(host.observations_count),
            _csv_safe(host.get_formal_outcome_display()),
            _csv_safe(host.get_status_display()),
        ])

    return response
