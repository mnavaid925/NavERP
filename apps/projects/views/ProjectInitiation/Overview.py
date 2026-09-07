"""Projects — module landing page.

The one page that is not an entity's list/detail/form, so it sits at the app's template root
(`templates/projects/overview.html`) rather than inside an entity folder.

It is a jumping-off point plus four counts, not a dashboard: 7.16 Reporting & Business
Intelligence owns project analytics, and a half-built dashboard here would compete with it.
"""
from apps.projects.models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render


@login_required
def overview(request):
    tenant = request.tenant
    return render(request, "projects/overview.html", {
        "request_count": ProjectRequest.objects.filter(tenant=tenant).count(),
        "awaiting_decision": ProjectRequest.objects.filter(
            tenant=tenant, status__in=ProjectRequest.DECISION_STATUSES).count(),
        "approved_unconverted": ProjectRequest.objects.filter(
            tenant=tenant, status="approved", converted_project__isnull=True).count(),
        "project_count": Project.objects.filter(tenant=tenant).count(),
        "active_projects": Project.objects.filter(tenant=tenant, status="active").count(),
        "stakeholder_count": ProjectStakeholder.objects.filter(tenant=tenant).count(),
        "kickoff_count": ProjectKickoff.objects.filter(tenant=tenant).count(),
    })
