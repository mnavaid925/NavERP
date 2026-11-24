from datetime import timedelta
from django.db.models import Count
from django.utils import timezone

from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert


def log_document_event(
    tenant,
    action_type,
    document=None,
    version=None,
    actor=None,
    request=None,
    details=None,
    is_success=True,
    failure_reason="",
):
    """Centralized helper for creating immutable document audit trail entries."""
    if not tenant:
        if document and getattr(document, "tenant", None):
            tenant = document.tenant
        elif request and getattr(request, "tenant", None):
            tenant = request.tenant

    if not actor and request and getattr(request, "user", None) and request.user.is_authenticated:
        actor = request.user

    ip_address = None
    user_agent = ""
    session_id = ""

    if request:
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
        if hasattr(request, "session") and request.session.session_key:
            session_id = request.session.session_key[:64]

    entry = DocumentAuditTrail.objects.create(
        tenant=tenant,
        document=document,
        version=version,
        actor=actor,
        action_type=action_type,
        is_success=is_success,
        failure_reason=failure_reason[:100],
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
        details_json=details or {},
    )
    return entry


def run_heuristic_anomaly_scan(tenant, hours=24):
    """Scan recent audit records and generate security alerts for anomalous patterns."""
    now = timezone.now()
    since = now - timedelta(hours=hours)
    created_count = 0

    # 1. Mass downloads
    downloads = (
        DocumentAuditTrail.objects.filter(
            tenant=tenant,
            event_timestamp__gte=since,
            action_type="downloaded",
            actor__isnull=False,
        )
        .values("actor")
        .annotate(cnt=Count("id"))
        .filter(cnt__gte=10)
    )

    for item in downloads:
        actor_id = item["actor"]
        cnt = item["cnt"]
        if not DocumentSecurityAlert.objects.filter(
            tenant=tenant, target_user_id=actor_id, alert_type="mass_download", detected_at__gte=since
        ).exists():
            DocumentSecurityAlert.objects.create(
                tenant=tenant,
                alert_type="mass_download",
                severity="high" if cnt < 25 else "critical",
                risk_score=min(95, 60 + cnt),
                title=f"Mass document download burst ({cnt} files)",
                description=f"User downloaded {cnt} documents in the past {hours} hours, exceeding normal threshold.",
                target_user_id=actor_id,
                event_count=cnt,
                status="new",
            )
            created_count += 1

    # 2. Permission denials
    denials = (
        DocumentAuditTrail.objects.filter(
            tenant=tenant,
            event_timestamp__gte=since,
            is_success=False,
            actor__isnull=False,
        )
        .values("actor")
        .annotate(cnt=Count("id"))
        .filter(cnt__gte=5)
    )

    for item in denials:
        actor_id = item["actor"]
        cnt = item["cnt"]
        if not DocumentSecurityAlert.objects.filter(
            tenant=tenant, target_user_id=actor_id, alert_type="excessive_denials", detected_at__gte=since
        ).exists():
            DocumentSecurityAlert.objects.create(
                tenant=tenant,
                alert_type="excessive_denials",
                severity="medium" if cnt < 10 else "high",
                risk_score=min(85, 45 + (cnt * 3)),
                title=f"Excessive access denial sequence ({cnt} events)",
                description=f"User triggered {cnt} authorization denials in past {hours} hours.",
                target_user_id=actor_id,
                event_count=cnt,
                status="new",
            )
            created_count += 1

    return created_count
