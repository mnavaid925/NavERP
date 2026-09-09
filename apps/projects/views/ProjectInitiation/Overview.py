"""Projects — module landing page.

The one page that is not an entity's list/detail/form, so it sits at the app's template root
(`templates/projects/overview.html`) rather than inside an entity folder.

It is a jumping-off point plus one count per table, not a dashboard: 7.16 Reporting & Business
Intelligence owns project analytics, and a half-built dashboard here would compete with it.
"""
from django.db.models import Count, Q

from apps.projects.models import (
    Project,
    ProjectKickoff,
    ProjectMilestone,
    ProjectRequest,
    ProjectStakeholder,
    ProjectTask,
    ResourceAllocation,
    ResourceProfile,
    ResourceTimeEntry,
    ScheduleBaseline,
    TaskDependency,
)
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render


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
    })
