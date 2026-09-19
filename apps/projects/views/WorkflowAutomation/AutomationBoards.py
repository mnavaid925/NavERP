"""Projects 7.17 — AutomationBoards views.

Computed operational dashboards for Workflow & Automation:
- automation_overview: Central automation health cockpit
- approval_inbox: Approver's focused queue
- recurrence_calendar: Forward projection of scheduled tasks
- webhook_diagnostics: iPaaS delivery health and failure analysis
"""
from datetime import timedelta
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.projects.models.WorkflowAutomation.ApprovalGates import ProjectApprovalGate
from apps.projects.models.WorkflowAutomation.RecurringTasks import RecurringTaskSchedule
from apps.projects.models.WorkflowAutomation.Webhooks import (
    ProjectWebhookDelivery,
    ProjectWebhookEndpoint,
)
from apps.projects.models.WorkflowAutomation.WorkflowRules import (
    ProjectWorkflowRule,
    WorkflowExecutionLog,
)
from apps.projects.views._common import *


@login_required
def automation_overview(request):
    """Central operational cockpit for automation health, rules, approvals, and webhooks."""
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    rules_agg = ProjectWorkflowRule.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    rules_count = rules_agg["total"] or 0
    active_rules = rules_agg["active"] or 0
    pending_gates_count = ProjectApprovalGate.objects.filter(tenant=request.tenant, status="pending").count()
    active_schedules = RecurringTaskSchedule.objects.filter(tenant=request.tenant, is_active=True).count()
    active_webhooks = ProjectWebhookEndpoint.objects.filter(tenant=request.tenant, is_active=True).count()
    deliveries_today = ProjectWebhookDelivery.objects.filter(tenant=request.tenant, attempted_at__gte=today_start).count()

    pending_gates = ProjectApprovalGate.objects.filter(
        tenant=request.tenant, status="pending"
    ).select_related("project", "approver")[:5]

    recent_logs = WorkflowExecutionLog.objects.filter(
        tenant=request.tenant
    ).select_related("rule")[:10]

    upcoming_recurring = RecurringTaskSchedule.objects.filter(
        tenant=request.tenant, is_active=True
    ).select_related("project", "default_assignee").order_by("next_run_date")[:5]

    return render(
        request,
        "projects/workflowautomation/boards/overview.html",
        {
            "stats": {
                "rules_count": rules_count,
                "active_rules": active_rules,
                "pending_gates": pending_gates_count,
                "active_schedules": active_schedules,
                "active_webhooks": active_webhooks,
                "deliveries_today": deliveries_today,
            },
            "pending_gates": pending_gates,
            "recent_logs": recent_logs,
            "upcoming_recurring": upcoming_recurring,
        },
    )


@login_required
def approval_inbox(request):
    """Focused inbox for the logged-in approver showing pending gates and delegations."""
    my_gates = ProjectApprovalGate.objects.filter(
        tenant=request.tenant,
        approver=request.user,
        status="pending",
    ).select_related("project", "requested_by")

    delegated_gates = ProjectApprovalGate.objects.filter(
        tenant=request.tenant,
        delegate_approver=request.user,
        status="pending",
    ).select_related("project", "requested_by", "approver")

    return render(
        request,
        "projects/workflowautomation/boards/approval_inbox.html",
        {
            "gates": my_gates,
            "delegated_gates": delegated_gates,
            "stats": {
                "my_pending": my_gates.count(),
                "delegated_pending": delegated_gates.count(),
            },
        },
    )


@login_required
def recurrence_calendar(request):
    """Forward calendar projection of upcoming recurring task generations."""
    today = timezone.localdate()
    month_end = today + timedelta(days=30)

    upcoming_schedules = RecurringTaskSchedule.objects.filter(
        tenant=request.tenant,
        is_active=True,
    ).select_related("project", "default_assignee").order_by("next_run_date")

    runs_this_month = RecurringTaskSchedule.objects.filter(
        tenant=request.tenant,
        is_active=True,
        next_run_date__gte=today,
        next_run_date__lte=month_end,
    ).count()

    return render(
        request,
        "projects/workflowautomation/boards/recurrence_calendar.html",
        {
            "upcoming_schedules": upcoming_schedules,
            "stats": {
                "total_recurring": upcoming_schedules.count(),
                "runs_this_month": runs_this_month,
            },
        },
    )


@login_required
def webhook_diagnostics(request):
    """Real-time iPaaS webhook delivery health, latency chart, and failure diagnostics."""
    endpoints = list(ProjectWebhookEndpoint.objects.filter(tenant=request.tenant).select_related("project"))
    total_endpoints = len(endpoints)
    active_endpoints = sum(1 for ep in endpoints if ep.is_active)

    delivery_stats = ProjectWebhookDelivery.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        successful=Count("id", filter=Q(status="success")),
        avg_latency=Avg("duration_ms"),
    )
    total_deliveries = delivery_stats["total"] or 0
    successful_deliveries = delivery_stats["successful"] or 0
    success_rate_pct = round((successful_deliveries / total_deliveries * 100), 1) if total_deliveries else 100.0

    avg_latency = delivery_stats["avg_latency"]
    avg_latency_ms = round(avg_latency, 1) if avg_latency else 0

    recent_failures = ProjectWebhookDelivery.objects.filter(
        tenant=request.tenant,
        status="failed",
    ).select_related("webhook").order_by("-attempted_at")[:10]

    return render(
        request,
        "projects/workflowautomation/boards/webhook_diagnostics.html",
        {
            "endpoints": endpoints,
            "recent_failures": recent_failures,
            "stats": {
                "total_endpoints": total_endpoints,
                "active_endpoints": active_endpoints,
                "success_rate_pct": success_rate_pct,
                "avg_latency_ms": avg_latency_ms,
            },
        },
    )
