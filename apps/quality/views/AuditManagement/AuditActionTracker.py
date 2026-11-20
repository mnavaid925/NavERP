from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.quality.models.AuditManagement.AuditFindings import AuditFinding
from apps.quality.views._common import quality_scope


@login_required
def audit_action_tracker(request):
    base_qs = quality_scope(
        AuditFinding.objects.select_related("audit", "audited_org_unit", "assignee", "linked_capa"),
        request,
    )

    open_findings = base_qs.exclude(status="closed").order_by("response_due_date")
    overdue_findings = base_qs.filter(
        response_due_date__lt=date.today(),
        status__in=["draft", "issued", "escalated"],
    ).order_by("response_due_date")
    pending_verification = base_qs.filter(status="verification_pending").order_by("-updated_at")

    stats = base_qs.aggregate(
        total_open=Count("id", filter=~Q(status="closed")),
        overdue=Count("id", filter=Q(response_due_date__lt=date.today(), status__in=["draft", "issued", "escalated"])),
        critical=Count("id", filter=~Q(status="closed") & Q(severity__in=["critical", "major"])),
        pending_verification=Count("id", filter=Q(status="verification_pending")),
    )

    context = {
        "open_findings": open_findings,
        "overdue_findings": overdue_findings,
        "pending_verification": pending_verification,
        "total_open_count": stats["total_open"],
        "overdue_count": stats["overdue"],
        "critical_count": stats["critical"],
        "pending_verification_count": stats["pending_verification"],
    }
    return render(request, "quality/auditmanagement/audit_action_tracker.html", context)
