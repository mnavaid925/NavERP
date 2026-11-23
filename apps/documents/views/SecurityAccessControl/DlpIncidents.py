from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.SecurityAccessControl.DlpIncidents import DlpIncidentResolveForm
from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident
from apps.documents.views._common import documents_object, documents_scope

PAGE_SIZE = 15


@login_required
def dlp_incident_list(request):
    qs = documents_scope(DlpIncident.objects.all(), request).select_related(
        "policy", "document", "triggered_by", "resolved_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(snippet_redacted__icontains=q)
            | Q(policy__name__icontains=q)
            | Q(document__title__icontains=q)
            | Q(triggered_by__username__icontains=q)
        )

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    resolution_status = request.GET.get("resolution_status", "").strip()
    if resolution_status:
        qs = qs.filter(resolution_status=resolution_status)

    policy_id = request.GET.get("policy", "").strip()
    if policy_id.isdigit():
        qs = qs.filter(policy_id=int(policy_id))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "incidents": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "paginator": paginator,
        "search_query": q,
        "severity": severity,
        "resolution_status": resolution_status,
        "severity_choices": DlpIncident.SEVERITY_CHOICES,
        "resolution_choices": DlpIncident.RESOLUTION_CHOICES,
    }
    return render(
        request,
        "documents/security_access_control/dlp_incident/list.html",
        context,
    )


@login_required
def dlp_incident_detail(request, pk):
    incident = documents_object(
        request,
        DlpIncident,
        pk,
        select_related=("policy", "document", "document_version", "triggered_by", "resolved_by"),
    )
    resolve_form = DlpIncidentResolveForm(instance=incident)

    context = {
        "incident": incident,
        "resolve_form": resolve_form,
    }
    return render(
        request,
        "documents/security_access_control/dlp_incident/detail.html",
        context,
    )


@login_required
@require_POST
def dlp_incident_resolve(request, pk):
    incident = documents_object(request, DlpIncident, pk)
    form = DlpIncidentResolveForm(request.POST, instance=incident)
    if form.is_valid():
        incident = form.save(commit=False)
        incident.resolved_by = request.user
        incident.save()
        write_audit_log(request.user, incident, "resolve", tenant=request.tenant)
        messages.success(request, f"DLP Incident {incident.number} resolved ({incident.get_resolution_status_display()}).")
    else:
        messages.error(request, "Failed to resolve incident. Please provide valid resolution notes.")
    return redirect(reverse("documents:dlp_incident_detail", kwargs={"pk": incident.pk}))
