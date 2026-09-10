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
    Project,
    ProjectExpense,
    ProjectIssue,
    ProjectKickoff,
    ProjectMilestone,
    ProjectRequest,
    ProjectRisk,
    ProjectStakeholder,
    ProjectTask,
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
        # 7.5 risk & issue — flat counts again. "Above tolerance" and "review due" are the two
        # figures that need a decision (they are what the monitoring page opens with), so they
        # are counted here rather than the raw register size. Both are Python-side because
        # `severity_band` and `is_review_overdue` are properties, not columns — the register is
        # small, and the alternative would be a duplicated band table.
        "risk_count": ProjectRisk.objects.filter(tenant=tenant).count(),
        "above_tolerance": sum(
            1 for risk in ProjectRisk.objects.filter(tenant=tenant)
            if risk.status not in ("realized", "closed")
            and risk.severity_band in ProjectRisk.TOLERANCE_BANDS),
        "review_due_count": sum(
            1 for risk in ProjectRisk.objects.filter(tenant=tenant) if risk.is_review_overdue),
        "issue_count": ProjectIssue.objects.filter(tenant=tenant).count(),
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
    })
