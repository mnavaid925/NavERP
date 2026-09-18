"""Projects 7.13 Agile & Scrum Management — Release Roadmap.

Realizes NavERP 7.13 bullet 3:
- Release & Version Planning (release trains, feature flags, version roadmap)
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.projects.models.AgileScrumManagement.ProjectReleases import ProjectRelease
from apps.projects.models.ProjectInitiation.Projects import Project


@login_required
def release_roadmap(request):
    """Visual timeline and milestone roadmap of upcoming and past releases across projects."""
    tenant = request.tenant
    projects = Project.objects.filter(tenant=tenant).order_by("name")

    project_id = as_db_int(request.GET.get("project"))
    selected_project = None
    if project_id:
        selected_project = projects.filter(pk=project_id).first()

    releases_qs = (
        ProjectRelease.objects.filter(tenant=tenant)
        .select_related("project", "released_by")
        .prefetch_related("tasks")
        .order_by("release_date", "id")
    )
    if selected_project:
        releases_qs = releases_qs.filter(project=selected_project)

    today = timezone.localdate()
    releases_list = list(releases_qs)

    total_count = len(releases_list)
    released_count = sum(1 for r in releases_list if r.status == "released")
    in_progress_count = sum(1 for r in releases_list if r.status == "in_progress")
    upcoming_count = sum(1 for r in releases_list if r.status == "unreleased")

    context = {
        "releases": releases_list,
        "projects": projects,
        "selected_project": selected_project,
        "today": today,
        "total_count": total_count,
        "released_count": released_count,
        "in_progress_count": in_progress_count,
        "upcoming_count": upcoming_count,
    }
    return render(request, "projects/agile/roadmap.html", context)
