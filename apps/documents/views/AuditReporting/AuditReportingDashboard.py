from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F
from django.shortcuts import render
from django.utils import timezone

from apps.documents.models.ApprovalWorkflow.DocumentApprovalRequests import DocumentApprovalRequest
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert
from apps.documents.models.VersionControl.Documents import Document


@login_required
def audit_dashboard(request):
    """Unified Audit & Security Command Center."""
    tenant = request.tenant
    now = timezone.now()
    since_24h = now - timedelta(hours=24)

    logs_24h = DocumentAuditTrail.objects.filter(tenant=tenant, event_timestamp__gte=since_24h)
    total_events_24h = logs_24h.count()
    downloads_24h = logs_24h.filter(action_type="downloaded").count()
    security_threats = DocumentSecurityAlert.objects.filter(
        tenant=tenant,
        status__in=["new", "investigating", "confirmed_threat"],
    ).count()

    # Fast verification on top 10 records
    chain_status = "intact"
    sample = list(DocumentAuditTrail.objects.filter(tenant=tenant).order_by("-id")[:10])
    for item in sample:
        if not item.verify_hash():
            chain_status = "compromised"
            break

    stats = {
        "total_events_24h": total_events_24h,
        "downloads_24h": downloads_24h,
        "security_threats": security_threats,
        "chain_status": chain_status,
    }

    recent_audit_logs = DocumentAuditTrail.objects.filter(tenant=tenant).select_related(
        "document", "actor"
    ).order_by("-event_timestamp")[:15]

    recent_alerts = DocumentSecurityAlert.objects.filter(
        tenant=tenant,
        status__in=["new", "investigating", "confirmed_threat"],
    ).select_related("target_user", "target_document").order_by("-detected_at")[:5]

    active_custody_passes = ChainOfCustodyExport.objects.filter(
        tenant=tenant,
        is_portal_active=True,
        expires_at__gt=now,
    ).select_related("document")[:5]

    context = {
        "stats": stats,
        "recent_audit_logs": recent_audit_logs,
        "recent_alerts": recent_alerts,
        "active_custody_passes": active_custody_passes,
    }
    return render(request, "documents/audit_reporting/audit_dashboard.html", context)


@login_required
def document_lifecycle_dashboard(request):
    """Document Lifecycle & Velocity Analytics: approval turnaround, bottlenecks, churn."""
    tenant = request.tenant

    # Status distribution
    status_distribution = list(
        Document.objects.filter(tenant=tenant)
        .values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # High churn documents (most versions)
    high_churn_docs = list(
        Document.objects.filter(tenant=tenant)
        .annotate(total_versions=Count("versions"))
        .filter(total_versions__gt=1)
        .order_by("-total_versions")[:10]
    )

    # Approval bottlenecks
    bottleneck_stages = []
    if DocumentApprovalRequest.objects.filter(tenant=tenant).exists():
        bottleneck_stages = list(
            DocumentApprovalRequest.objects.filter(tenant=tenant)
            .values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    lifecycle_kpis = {
        "status_distribution": status_distribution,
        "high_churn_docs": high_churn_docs,
        "bottleneck_stages": bottleneck_stages,
        "total_managed_docs": Document.objects.filter(tenant=tenant).count(),
    }

    context = {
        "lifecycle_kpis": lifecycle_kpis,
    }
    return render(request, "documents/audit_reporting/lifecycle_dashboard.html", context)
