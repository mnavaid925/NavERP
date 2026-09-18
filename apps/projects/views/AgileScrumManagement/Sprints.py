"""Projects 7.13 Agile & Scrum Management — Sprint views.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.projects.forms.AgileScrumManagement.Sprints import SprintForm
from apps.projects.models.AgileScrumManagement.Sprints import Sprint
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def spt_list(request):
    qs = (
        Sprint.objects.filter(tenant=request.tenant)
        .select_related("project", "scrum_master")
        .prefetch_related("tasks", "impediments")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/agile/sprint/list.html",
        search_fields=["name", "goal", "standup_notes"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "sprints": qs,
            "status_choices": Sprint.STATUS_CHOICES,
            "projects": projects,
            "selected_project_id": project_id,
            "total_count": qs.count(),
        },
    )


@login_required
def spt_create(request):
    return crud_create(
        request,
        form_class=SprintForm,
        template="projects/agile/sprint/form.html",
        success_url="projects:spt_list",
    )


@login_required
def spt_detail(request, pk):
    sprint = get_object_or_404(
        Sprint.objects.select_related("project", "scrum_master"),
        pk=pk,
        tenant=request.tenant,
    )
    tasks = sprint.tasks.select_related("assignee", "epic").order_by("sequence", "id")
    impediments = sprint.impediments.select_related("owner").order_by("-created_at")

    total_pts = sprint.total_points
    completed_pts = sprint.completed_points
    rem_pts = sprint.remaining_points
    burndown_data = {
        "total_points": total_pts,
        "committed_points": sprint.committed_points or total_pts,
        "completed_points": completed_pts,
        "remaining_points": rem_pts,
        "completion_rate": sprint.completion_rate,
    }

    return render(
        request,
        "projects/agile/sprint/detail.html",
        {
            "obj": sprint,
            "sprint": sprint,
            "tasks": tasks,
            "impediments": impediments,
            "burndown_data": burndown_data,
        },
    )


@login_required
def spt_edit(request, pk):
    return crud_edit(
        request,
        model=Sprint,
        pk=pk,
        form_class=SprintForm,
        template="projects/agile/sprint/form.html",
        success_url="projects:spt_list",
    )


@login_required
@require_POST
def spt_delete(request, pk):
    return crud_delete(
        request,
        model=Sprint,
        pk=pk,
        success_url="projects:spt_list",
    )


@login_required
@require_POST
def spt_start(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk, tenant=request.tenant)
    if sprint.status != "planning":
        messages.error(
            request,
            f"Sprint {sprint.number} cannot be started from status '{sprint.get_status_display()}'.",
        )
        return redirect("projects:spt_detail", pk=pk)

    sprint.status = "active"
    sprint.started_at = timezone.now()
    sprint.committed_points = sprint.total_points
    sprint.save(
        update_fields=["status", "started_at", "committed_points", "updated_at"]
    )
    write_audit_log(request.user, sprint, "start")
    messages.success(
        request,
        f"Sprint {sprint.number} started with {sprint.committed_points} committed points.",
    )
    return redirect("projects:spt_detail", pk=pk)


@login_required
@require_POST
def spt_complete(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk, tenant=request.tenant)
    if sprint.status != "active":
        messages.error(
            request,
            f"Sprint {sprint.number} cannot be completed from status '{sprint.get_status_display()}'.",
        )
        return redirect("projects:spt_detail", pk=pk)

    sprint.status = "completed"
    sprint.completed_at = timezone.now()
    sprint.save(update_fields=["status", "completed_at", "updated_at"])
    write_audit_log(request.user, sprint, "complete")
    messages.success(
        request,
        f"Sprint {sprint.number} marked completed ({sprint.completed_points}/{sprint.total_points} pts delivered).",
    )
    return redirect("projects:spt_detail", pk=pk)


@login_required
@require_POST
def spt_cancel(request, pk):
    sprint = get_object_or_404(Sprint, pk=pk, tenant=request.tenant)
    sprint.status = "cancelled"
    sprint.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, sprint, "cancel")
    messages.warning(request, f"Sprint {sprint.number} was cancelled.")
    return redirect("projects:spt_detail", pk=pk)
