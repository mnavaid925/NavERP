from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, ExpressionWrapper, F, Q, fields
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

    # Consolidate request counts into single aggregate query
    req_stats = req_qs.aggregate(
        pending_signoffs=Count("id", filter=Q(status="pending")),
        escalated_count=Count("id", filter=Q(is_escalated=True)),
        total_decided=Count("id", filter=Q(status__in=["approved", "rejected"])),
    )
    pending_signoffs = req_stats["pending_signoffs"] or 0
    escalated_count = req_stats["escalated_count"] or 0
    total_decided = req_stats["total_decided"] or 0
    escalation_rate_pct = round((escalated_count / total_decided * 100), 1) if total_decided > 0 else 0.0

    # Compute average turnaround hours for completed workflows using DB aggregate
    duration_expr = ExpressionWrapper(
        F("completed_at") - F("created_at"),
        output_field=fields.DurationField(),
    )
    avg_delta = (
        wf_qs.filter(status="approved", completed_at__isnull=False)
        .annotate(duration=duration_expr)
        .aggregate(avg_dur=Avg("duration"))["avg_dur"]
    )
    avg_cycle_time_hours = round(avg_delta.total_seconds() / 3600.0, 1) if avg_delta is not None else 24.0

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
