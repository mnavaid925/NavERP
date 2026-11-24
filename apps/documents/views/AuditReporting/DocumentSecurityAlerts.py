from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.AuditReporting.DocumentSecurityAlerts import (
    DocumentSecurityAlertFilterForm,
    DocumentSecurityAlertTriageForm,
)
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert
from apps.documents.services.audit import run_heuristic_anomaly_scan

PAGE_SIZE = 15


@login_required
def security_alert_list(request):
    """List User Behavior Analytics (UBA) security alerts with severity tabs and search."""
    qs = DocumentSecurityAlert.objects.filter(tenant=request.tenant).select_related(
        "target_user", "target_document", "assigned_to"
    )

    filter_form = DocumentSecurityAlertFilterForm(request.GET)
    q = request.GET.get("q", "").strip()
    severity = request.GET.get("severity", "").strip()
    status = request.GET.get("status", "").strip()
    alert_type = request.GET.get("alert_type", "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(number__icontains=q)
            | Q(source_ip__icontains=q)
            | Q(triage_notes__icontains=q)
        )
    if severity:
        qs = qs.filter(severity=severity)
    if status:
        qs = qs.filter(status=status)
    if alert_type:
        qs = qs.filter(alert_type=alert_type)

    open_count = DocumentSecurityAlert.objects.filter(
        tenant=request.tenant,
        status__in=["new", "investigating", "confirmed_threat"],
    ).count()

    critical_count = DocumentSecurityAlert.objects.filter(
        tenant=request.tenant,
        severity="critical",
        status__in=["new", "investigating", "confirmed_threat"],
    ).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "alerts": page_obj.object_list,
        "page_obj": page_obj,
        "filter_form": filter_form,
        "open_count": open_count,
        "critical_count": critical_count,
        "severity_choices": DocumentSecurityAlert.SEVERITY_CHOICES,
        "status_choices": DocumentSecurityAlert.STATUS_CHOICES,
        "alert_type_choices": DocumentSecurityAlert.ALERT_TYPE_CHOICES,
    }
    return render(request, "documents/audit_reporting/security_alert/list.html", context)


@login_required
def security_alert_detail(request, pk):
    """Investigation workbench for a specific security alert incident."""
    alert = get_object_or_404(
        DocumentSecurityAlert.objects.select_related("target_user", "target_document", "assigned_to", "resolved_by"),
        pk=pk,
        tenant=request.tenant,
    )

    triage_form = DocumentSecurityAlertTriageForm(tenant=request.tenant, instance=alert)

    # Correlated audit logs for this target user
    correlated_audit_logs = []
    target_user_stats = {}
    if alert.target_user:
        logs_qs = DocumentAuditTrail.objects.filter(
            tenant=request.tenant,
            actor=alert.target_user,
        ).order_by("-event_timestamp")
        correlated_audit_logs = list(logs_qs[:25])
        target_user_stats = {
            "total_events": logs_qs.count(),
            "download_count": logs_qs.filter(action_type="downloaded").count(),
            "denied_count": logs_qs.filter(is_success=False).count(),
        }

    context = {
        "alert": alert,
        "triage_form": triage_form,
        "correlated_audit_logs": correlated_audit_logs,
        "target_user_stats": target_user_stats,
    }
    return render(request, "documents/audit_reporting/security_alert/detail.html", context)


@require_POST
@tenant_admin_required
def security_alert_triage(request, pk):
    """Process triage update for a security alert incident."""
    alert = get_object_or_404(DocumentSecurityAlert, pk=pk, tenant=request.tenant)

    form = DocumentSecurityAlertTriageForm(tenant=request.tenant, data=request.POST, instance=alert)
    if form.is_valid():
        updated_alert = form.save(commit=False)
        if updated_alert.status in ("resolved", "dismissed") and not updated_alert.resolved_at:
            updated_alert.resolved_at = timezone.now()
            updated_alert.resolved_by = request.user
        elif updated_alert.status not in ("resolved", "dismissed"):
            updated_alert.resolved_at = None
            updated_alert.resolved_by = None

        updated_alert.save()
        write_audit_log(request.user, updated_alert, "triage", tenant=request.tenant)
        messages.success(request, f"Security alert #{alert.number} triage updated to '{alert.get_status_display()}'.")
    else:
        messages.error(request, "Failed to update triage. Please check form values.")

    return redirect("documents:security_alert_detail", pk=alert.pk)


@require_POST
@tenant_admin_required
def security_alert_scan(request):
    """Run an on-demand heuristic anomaly detection scan over recent audit activity."""
    created_alerts = run_heuristic_anomaly_scan(request.tenant, hours=24)
    write_audit_log(request.user, None, "scan", tenant=request.tenant)

    if created_alerts > 0:
        messages.warning(request, f"Heuristic anomaly scan completed: {created_alerts} new security alert(s) generated.")
    else:
        messages.success(request, "Heuristic anomaly scan completed: No abnormal behavioral patterns detected in past 24 hours.")

    return redirect("documents:security_alert_list")
