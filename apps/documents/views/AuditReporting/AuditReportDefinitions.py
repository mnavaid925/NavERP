import csv
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.AuditReporting.AuditReportDefinitions import AuditReportDefinitionForm
from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.views._common import _csv_safe


@login_required
def audit_report_list(request):
    """List compliance report presets and custom user audit report definitions."""
    qs = AuditReportDefinition.objects.filter(tenant=request.tenant).select_related("created_by", "last_run_by")

    report_type = request.GET.get("report_type", "").strip()
    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(number__icontains=q))
    if report_type:
        qs = qs.filter(report_type=report_type)
    if status:
        qs = qs.filter(status=status)

    system_reports = list(qs.filter(is_system_preset=True).order_by("name"))
    custom_reports = list(qs.filter(is_system_preset=False).order_by("-created_at"))
    total_reports = len(system_reports) + len(custom_reports)

    context = {
        "system_reports": system_reports,
        "custom_reports": custom_reports,
        "total_reports": total_reports,
        "system_count": len(system_reports),
        "custom_count": len(custom_reports),
        "report_type_choices": AuditReportDefinition.REPORT_TYPE_CHOICES,
        "status_choices": AuditReportDefinition.STATUS_CHOICES,
    }
    return render(request, "documents/audit_reporting/report_definition/list.html", context)


@login_required
def audit_report_create(request):
    """Create a new custom audit report definition."""
    if request.method == "POST":
        form = AuditReportDefinitionForm(request.POST)
        if form.is_valid():
            report_def = form.save(commit=False)
            report_def.tenant = request.tenant
            report_def.created_by = request.user
            report_def.is_system_preset = False
            report_def.save()
            write_audit_log(request.user, report_def, "create", tenant=request.tenant)
            messages.success(request, f"Audit report definition '{report_def.name}' created.")
            return redirect("documents:audit_report_detail", pk=report_def.pk)
    else:
        form = AuditReportDefinitionForm()

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "documents/audit_reporting/report_definition/form.html", context)


@login_required
def audit_report_detail(request, pk):
    """Execute and render the audit report with aggregated KPI metrics and data tables."""
    report_def = get_object_or_404(AuditReportDefinition, pk=pk, tenant=request.tenant)

    start_dt, end_dt = report_def.get_effective_date_range()
    events_qs = DocumentAuditTrail.objects.filter(
        tenant=request.tenant,
        event_timestamp__range=(start_dt, end_dt),
    ).select_related("document", "actor", "version")

    # Filter according to report type
    rtype = report_def.report_type
    if rtype == "confidential_access":
        events_qs = events_qs.filter(action_type__in=["viewed", "previewed", "downloaded", "printed"])
    elif rtype == "permission_audit":
        events_qs = events_qs.filter(action_type="permission_changed")
    elif rtype == "security_exceptions":
        events_qs = events_qs.filter(Q(is_success=False) | Q(action_type="dlp_violation"))
    elif rtype == "external_sharing":
        events_qs = events_qs.filter(action_type__in=["shared_externally", "share_revoked"])
    elif rtype == "deletion_purge":
        events_qs = events_qs.filter(action_type__in=["deleted", "purged"])
    elif rtype == "lifecycle_bottlenecks":
        events_qs = events_qs.filter(action_type__in=["workflow_approved", "workflow_rejected"])
    elif rtype == "version_churn":
        events_qs = events_qs.filter(action_type="version_uploaded")

    agg = events_qs.aggregate(
        total_events=Count("id"),
        failed_events=Count("id", filter=Q(is_success=False)),
        unique_actors=Count("actor", distinct=True),
    )
    total_events = agg["total_events"] or 0
    failed_events = agg["failed_events"] or 0
    success_events = total_events - failed_events
    success_rate = round((success_events / total_events * 100), 1) if total_events > 0 else 100.0
    unique_actors = agg["unique_actors"] or 0

    summary_kpis = {
        "total_events": total_events,
        "success_events": success_events,
        "failed_events": failed_events,
        "success_rate": success_rate,
        "unique_actors": unique_actors,
    }

    # Update execution counter
    report_def.last_run_at = timezone.now()
    report_def.last_run_by = request.user
    report_def.total_runs += 1
    report_def.save(update_fields=["last_run_at", "last_run_by", "total_runs"])

    # Limit in-memory rendering table to first 200 records
    report_data = list(events_qs[:200])

    context = {
        "report_def": report_def,
        "report_data": report_data,
        "summary_kpis": summary_kpis,
        "date_start": start_dt,
        "date_end": end_dt,
        "total_events": total_events,
    }
    return render(request, "documents/audit_reporting/report_definition/detail.html", context)


@login_required
def audit_report_edit(request, pk):
    """Edit an existing custom audit report definition."""
    report_def = get_object_or_404(AuditReportDefinition, pk=pk, tenant=request.tenant)

    if report_def.is_system_preset:
        messages.error(request, "System preset report definitions cannot be modified.")
        return redirect("documents:audit_report_detail", pk=report_def.pk)

    if request.method == "POST":
        form = AuditReportDefinitionForm(request.POST, instance=report_def)
        if form.is_valid():
            report = form.save()
            write_audit_log(request.user, report, "update", tenant=request.tenant)
            messages.success(request, f"Audit report '{report.name}' updated.")
            return redirect("documents:audit_report_detail", pk=report.pk)
    else:
        form = AuditReportDefinitionForm(instance=report_def)

    context = {
        "form": form,
        "report_def": report_def,
        "is_edit": True,
    }
    return render(request, "documents/audit_reporting/report_definition/form.html", context)


@login_required
@require_POST
def audit_report_delete(request, pk):
    """Delete a custom audit report definition."""
    report_def = get_object_or_404(AuditReportDefinition, pk=pk, tenant=request.tenant)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    is_creator = report_def.created_by_id == request.user.pk
    if not (is_admin or is_creator):
        raise PermissionDenied("Only the creator or a tenant administrator can delete this report.")

    if report_def.is_system_preset:
        messages.error(request, "System preset report definitions cannot be deleted.")
        return redirect("documents:audit_report_list")

    name = report_def.name
    write_audit_log(request.user, report_def, "delete", tenant=request.tenant)
    report_def.delete()
    messages.success(request, f"Audit report definition '{name}' deleted.")
    return redirect("documents:audit_report_list")


@login_required
def audit_report_run(request, pk):
    """Run report and return full downloadable CSV or JSON export."""
    report_def = get_object_or_404(AuditReportDefinition, pk=pk, tenant=request.tenant)
    fmt = request.GET.get("format", report_def.output_format).lower()

    start_dt, end_dt = report_def.get_effective_date_range()
    events_qs = DocumentAuditTrail.objects.filter(
        tenant=request.tenant,
        event_timestamp__range=(start_dt, end_dt),
    ).select_related("document", "actor")

    rtype = report_def.report_type
    if rtype == "confidential_access":
        events_qs = events_qs.filter(action_type__in=["viewed", "previewed", "downloaded", "printed"])
    elif rtype == "permission_audit":
        events_qs = events_qs.filter(action_type="permission_changed")
    elif rtype == "security_exceptions":
        events_qs = events_qs.filter(Q(is_success=False) | Q(action_type="dlp_violation"))
    elif rtype == "external_sharing":
        events_qs = events_qs.filter(action_type__in=["shared_externally", "share_revoked"])
    elif rtype == "deletion_purge":
        events_qs = events_qs.filter(action_type__in=["deleted", "purged"])
    elif rtype == "lifecycle_bottlenecks":
        events_qs = events_qs.filter(action_type__in=["workflow_approved", "workflow_rejected"])
    elif rtype == "version_churn":
        events_qs = events_qs.filter(action_type="version_uploaded")

    write_audit_log(request.user, report_def, "export", tenant=request.tenant)

    if fmt == "json":
        data = []
        for e in events_qs[:2000]:
            data.append({
                "number": e.number,
                "timestamp": e.event_timestamp.isoformat() if e.event_timestamp else None,
                "action": e.action_type,
                "is_success": e.is_success,
                "document": e.document_number_snapshot or (e.document.number if e.document else None),
                "actor": e.actor_email_snapshot or (e.actor.email if e.actor else None),
                "ip_address": e.ip_address,
                "chain_hash": e.chain_hash,
            })
        response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="report_{report_def.number}.json"'
        return response

    # Default CSV
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="report_{report_def.number}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Entry #", "Timestamp", "Action", "Result", "Document #", "Document Title", "Actor", "IP", "Chain Hash"])
    for e in events_qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(e.number),
            _csv_safe(e.event_timestamp.isoformat() if e.event_timestamp else ""),
            _csv_safe(e.get_action_type_display()),
            _csv_safe("Success" if e.is_success else "Failed/Blocked"),
            _csv_safe(e.document_number_snapshot or (e.document.number if e.document else "")),
            _csv_safe(e.document_title_snapshot or (e.document.title if e.document else "")),
            _csv_safe(e.actor_email_snapshot or (e.actor.email if e.actor else "")),
            _csv_safe(e.ip_address or ""),
            _csv_safe(e.chain_hash),
        ])
    return response
