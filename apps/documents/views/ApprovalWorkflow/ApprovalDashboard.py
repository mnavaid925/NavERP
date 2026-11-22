from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q
from django.shortcuts import render
from django.utils import timezone

from apps.documents.models import (
    DocumentApprovalRequest,
    DocumentApprovalWorkflow,
    DocumentReviewComment,
    DocumentSignature,
)
from apps.documents.views._common import documents_scope


@login_required
def approval_dashboard(request):
    wf_qs = documents_scope(DocumentApprovalWorkflow.objects.all(), request)
    req_qs = documents_scope(DocumentApprovalRequest.objects.all(), request)
    sig_qs = documents_scope(DocumentSignature.objects.all(), request)
    comm_qs = documents_scope(DocumentReviewComment.objects.all(), request)

    total_active_workflows = wf_qs.filter(status__in=["pending", "escalated"]).count()
    pending_signoffs = req_qs.filter(status="pending").count()
    escalated_count = req_qs.filter(is_escalated=True).count()
    total_decided = req_qs.filter(status__in=["approved", "rejected"]).count()
    escalation_rate_pct = round((escalated_count / total_decided * 100), 1) if total_decided > 0 else 0.0

    # Compute average turnaround hours for completed workflows
    completed_wfs = wf_qs.filter(status="approved", completed_at__isnull=False)
    total_hours = 0
    count_comp = 0
    for w in completed_wfs[:50]:
        delta = w.completed_at - w.created_at
        total_hours += delta.total_seconds() / 3600.0
        count_comp += 1
    avg_cycle_time_hours = round(total_hours / count_comp, 1) if count_comp > 0 else 24.0

    pending_workflows = (
        wf_qs.filter(status__in=["pending", "escalated"])
        .select_related("document", "initiator", "department")
        .order_by("due_date", "-created_at")[:10]
    )

    urgent_requests = (
        req_qs.filter(status="pending", workflow__urgency__in=["high", "urgent"])
        .select_related("workflow", "workflow__document", "approver")
        .order_by("due_date", "-created_at")[:10]
    )

    recent_signatures = (
        sig_qs.select_related("document", "signer")
        .order_by("-signed_at")[:8]
    )

    blocking_comments = (
        comm_qs.filter(is_blocking=True, status="open")
        .select_related("document", "workflow", "author")
        .order_by("-created_at")[:8]
    )

    context = {
        "pending_workflows": pending_workflows,
        "urgent_requests": urgent_requests,
        "recent_signatures": recent_signatures,
        "blocking_comments": blocking_comments,
        "metrics": {
            "total_active_workflows": total_active_workflows,
            "avg_cycle_time_hours": avg_cycle_time_hours,
            "escalation_rate_pct": escalation_rate_pct,
            "pending_signoffs": pending_signoffs,
        },
    }
    return render(request, "documents/approval_workflow/approval_dashboard.html", context)
