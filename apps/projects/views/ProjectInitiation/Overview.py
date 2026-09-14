"""Projects — module landing page.

The one page that is not an entity's list/detail/form, so it sits at the app's template root
(`templates/projects/overview.html`) rather than inside an entity folder.

It is a jumping-off point plus one count per table, not a dashboard: 7.16 Reporting & Business
Intelligence owns project analytics, and a half-built dashboard here would compete with it.
"""
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.projects.models import (
    BudgetRevision,
    Channel,
    DeliverableInspection,
    Meeting,
    MeetingActionItem,
    Project,
    ProjectExpense,
    ProjectIssue,
    ProjectKickoff,
    ProjectMilestone,
    ProjectNotification,
    ProjectRequest,
    ProjectRisk,
    ProjectStakeholder,
    ProjectTask,
    QualityDefect,
    QualityPlan,
    Requirement,
    ResourceAllocation,
    ResourceProfile,
    ResourceTimeEntry,
    ScheduleBaseline,
    ScopeChangeRequest,
    ScopeVerification,
    TaskDependency,
)
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render

_MONEY = DecimalField(max_digits=20, decimal_places=2)


@login_required
def overview(request):
    tenant = request.tenant
    # ONE aggregate per TABLE, not one query per card: the five request/project counts are
    # conditional counts over the same two row sets, so `Count("pk", filter=Q(...))` collapses
    # 7 round trips to 4 (the floor — four tables) with identical values. `converted_project`
    # is a column on the request itself, so the isnull filter adds no join. The 7.2 tables are
    # flat counts — one COUNT each, no join they could share.
    requests = ProjectRequest.objects.filter(tenant=tenant).aggregate(
        total=Count("pk"),
        awaiting=Count("pk", filter=Q(status__in=ProjectRequest.DECISION_STATUSES)),
        ready=Count("pk", filter=Q(status="approved", converted_project__isnull=True)),
    )
    projects = Project.objects.filter(tenant=tenant).aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(status="active")),
    )
    # 7.5 risk & issue — the three risk figures come off ONE materialised register rather than
    # three querysets, because `severity_band` and `is_review_overdue` are properties, not
    # columns. The register is small and the landing page is the most-hit page in the module.
    register = list(ProjectRisk.objects.filter(tenant=tenant))
    risk_count = len(register)
    above_tolerance = sum(
        1 for risk in register
        if risk.status not in ("realized", "closed")
        and risk.severity_band in ProjectRisk.TOLERANCE_BANDS)
    review_due_count = sum(1 for risk in register if risk.is_review_overdue)
    # 7.8's blocked figure is derived (`is_blocked` — dependency- or manually-blocked), so no
    # column filter can count it: materialize the LIVE task list once (the `risk_count` shape
    # above) and count the blocked rows in Python — finished work stays out, matching the board.
    live_tasks = list(ProjectTask.objects.filter(
        tenant=tenant, status__in=("planned", "in_progress")))
    blocked_task_count = sum(1 for task in live_tasks if task.is_blocked)
    return render(request, "projects/overview.html", {
        "request_count": requests["total"],
        "awaiting_decision": requests["awaiting"],
        "approved_unconverted": requests["ready"],
        "project_count": projects["total"],
        "active_projects": projects["active"],
        "stakeholder_count": ProjectStakeholder.objects.filter(tenant=tenant).count(),
        "kickoff_count": ProjectKickoff.objects.filter(tenant=tenant).count(),
        "task_count": ProjectTask.objects.filter(tenant=tenant).count(),
        "dependency_count": TaskDependency.objects.filter(tenant=tenant).count(),
        "milestone_count": ProjectMilestone.objects.filter(tenant=tenant).count(),
        "baseline_count": ScheduleBaseline.objects.filter(tenant=tenant).count(),
        # 7.3 resourcing — flat counts, same one-COUNT-per-table rule.
        "resource_count": ResourceProfile.objects.filter(tenant=tenant).count(),
        "allocation_count": ResourceAllocation.objects.filter(tenant=tenant).count(),
        "time_entry_count": ResourceTimeEntry.objects.filter(tenant=tenant).count(),
        # 7.4 cost & budget — one aggregate per table: the pending-approval COUNT is the
        # approval queue's depth, and the posted-spend SUM is the money already burning
        # (posted actuals + accruals; commitments and drafts don't count).
        "pending_revisions": BudgetRevision.objects.filter(
            tenant=tenant, status="pending_approval").count(),
        "posted_spend": ProjectExpense.objects.filter(tenant=tenant).aggregate(
            total=Coalesce(
                Sum("amount", filter=Q(status="posted",
                                       entry_type__in=("actual", "accrual"))),
                Value(Decimal("0")), output_field=_MONEY))["total"],
        # 7.5 risk & issue — the register size plus the two figures that need a decision
        # ("above tolerance" and "review due" are what the monitoring page opens with), all
        # derived from the one materialised register above.
        "risk_count": risk_count,
        "above_tolerance": above_tolerance,
        "review_due_count": review_due_count,
        "issue_count": ProjectIssue.objects.filter(tenant=tenant).count(),
        # 7.6 quality — the plan register's size plus the two figures that need a decision: the
        # acceptance inspections still awaiting a usage decision (the acceptance board's queue)
        # and the open punch list (what stands between a conditional acceptance and sign-off).
        "quality_plan_count": QualityPlan.objects.filter(tenant=tenant).count(),
        "acceptance_queue_count": DeliverableInspection.objects.filter(
            tenant=tenant, inspection_type="acceptance", usage_decision="pending").count(),
        "open_defect_count": QualityDefect.objects.filter(
            tenant=tenant, status__in=("open", "in_progress")).count(),
        # 7.7 scope & requirements — flat counts again, plus the two figures that need a decision:
        # the requirements nobody has linked to a delivering work package (the traceability gap) and
        # the change requests still in front of the board. Both are plain column filters, so no
        # Python-side pass is needed here.
        "requirement_count": Requirement.objects.filter(tenant=tenant).count(),
        "untraced_count": Requirement.objects.filter(tenant=tenant,
                                                     wbs_node__isnull=True).count(),
        "scope_change_count": ScopeChangeRequest.objects.filter(tenant=tenant).count(),
        "pending_change_count": ScopeChangeRequest.objects.filter(
            tenant=tenant, status__in=("draft", "submitted", "under_review")).count(),
        "pending_verification_count": ScopeVerification.objects.filter(
            tenant=tenant, acceptance_status="pending").count(),
        # 7.8 task & work — the pinned trio (§7.5): `in_progress` a DB count, `blocked` the
        # derived figure over the materialized live list above (a dependency-blocked task with
        # no manual block counts too), and the overdue tasks (the execution debt) as a plain
        # column filter. The register-wide count is the pre-existing "WBS nodes" card — no
        # duplicate Tasks card.
        "in_progress_task_count": ProjectTask.objects.filter(
            tenant=tenant, status="in_progress").count(),
        "blocked_task_count": blocked_task_count,
        "overdue_task_count": ProjectTask.objects.filter(
            tenant=tenant, status__in=("planned", "in_progress"),
            planned_end__lt=timezone.localdate()).count(),
        # 7.9 collaboration & communication — three flat per-table counts (one COUNT each, no join
        # they could share) plus the reader's OWN unread inbox depth. That last one is scoped to
        # `request.user` on purpose: an inbox is personal, so the card reports what this reader has
        # not read, not what the workspace has sent.
        "channel_count": Channel.objects.filter(tenant=tenant).count(),
        "meeting_count": Meeting.objects.filter(tenant=tenant).count(),
        "open_action_count": MeetingActionItem.objects.filter(
            tenant=tenant, is_done=False).count(),
        "unread_notification_count": ProjectNotification.objects.filter(
            tenant=tenant, recipient=request.user, is_read=False).count(),
    })
