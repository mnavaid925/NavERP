"""Projects 7.13 Agile & Scrum Management — ProjectRelease views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.projects.forms.AgileScrumManagement.ProjectReleases import ProjectReleaseForm
from apps.projects.models.AgileScrumManagement.ProjectReleases import ProjectRelease
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def rel_list(request):
    qs = (
        ProjectRelease.objects.filter(tenant=request.tenant)
        .select_related("project", "released_by")
        .prefetch_related("tasks")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/agile/release/list.html",
        search_fields=["name", "version_tag", "release_notes"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "releases": qs,
            "status_choices": ProjectRelease.STATUS_CHOICES,
            "projects": projects,
            "selected_project_id": project_id,
            "total_count": qs.count(),
        },
    )


@login_required
def rel_create(request):
    return crud_create(
        request,
        form_class=ProjectReleaseForm,
        template="projects/agile/release/form.html",
        success_url="projects:rel_list",
    )


@login_required
def rel_detail(request, pk):
    release = get_object_or_404(
        ProjectRelease.objects.select_related("project", "released_by"),
        pk=pk,
        tenant=request.tenant,
    )
    tasks = release.tasks.select_related("assignee", "sprint", "epic").order_by(
        "sequence", "id"
    )

    return render(
        request,
        "projects/agile/release/detail.html",
        {
            "obj": release,
            "release": release,
            "tasks": tasks,
        },
    )


@login_required
def rel_edit(request, pk):
    return crud_edit(
        request,
        model=ProjectRelease,
        pk=pk,
        form_class=ProjectReleaseForm,
        template="projects/agile/release/form.html",
        success_url="projects:rel_list",
    )


@login_required
@require_POST
def rel_delete(request, pk):
    return crud_delete(
        request,
        model=ProjectRelease,
        pk=pk,
        success_url="projects:rel_list",
    )


@login_required
@require_POST
def rel_publish(request, pk):
    release = get_object_or_404(ProjectRelease, pk=pk, tenant=request.tenant)
    if release.status == "released":
        messages.info(request, f"Release {release.version_tag} is already published.")
        return redirect("projects:rel_detail", pk=pk)

    release.status = "released"
    release.released_at = timezone.now()
    release.released_by = request.user
    release.save(update_fields=["status", "released_at", "released_by", "updated_at"])

    write_audit_log(request.user, "publish", release)
    messages.success(
        request,
        f"Release {release.version_tag} ({release.name}) published successfully.",
    )
    return redirect("projects:rel_detail", pk=pk)
