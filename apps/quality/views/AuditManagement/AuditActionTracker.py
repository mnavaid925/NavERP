from datetime import date

from django.contrib.auth.decorators import login_required
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
    overdue_findings = [f for f in open_findings if f.is_overdue]
    pending_verification = base_qs.filter(status="verification_pending").order_by("-updated_at")
    escalated_findings = base_qs.filter(status="escalated").order_by("-updated_at")

    total_open_count = len(open_findings)
    overdue_count = len(overdue_findings)
    critical_count = sum(1 for f in open_findings if f.severity in ("critical", "major"))
    pending_verification_count = pending_verification.count()

    context = {
        "open_findings": open_findings,
        "overdue_findings": overdue_findings,
        "pending_verification": pending_verification,
        "escalated_findings": escalated_findings,
        "total_open_count": total_open_count,
        "overdue_count": overdue_count,
        "critical_count": critical_count,
        "pending_verification_count": pending_verification_count,
    }
    return render(request, "quality/auditmanagement/audit_action_tracker.html", context)
