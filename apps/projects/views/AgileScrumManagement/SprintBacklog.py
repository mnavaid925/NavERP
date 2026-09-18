"""Projects 7.13 Agile & Scrum Management — Sprint Backlog & Grooming Workbench.

Realizes NavERP 7.13 bullet 1:
- Sprint Planning & Backlog Grooming (story point estimation, velocity tracking, backlog prioritization)
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.projects.models.AgileScrumManagement.ProjectEpics import ProjectEpic
from apps.projects.models.AgileScrumManagement.ProjectReleases import ProjectRelease
from apps.projects.models.AgileScrumManagement.Sprints import Sprint
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask


@login_required
def sprint_backlog(request):
    """Backlog grooming workbench for story point estimation, sprint allocation, and prioritization."""
    tenant = request.tenant
    projects = Project.objects.filter(tenant=tenant).order_by("name")

    project_id = as_db_int(request.GET.get("project"))
    selected_project = None
    if project_id:
        selected_project = projects.filter(pk=project_id).first()

    if request.method == "POST":
        action = request.POST.get("action")
        task_id = as_db_int(request.POST.get("task_id"))
        task = get_object_or_404(ProjectTask, pk=task_id, tenant=tenant)

        if action == "assign_sprint":
            sprint_id = as_db_int(request.POST.get("sprint_id"))
            target_sprint = None
            if sprint_id:
                target_sprint = get_object_or_404(Sprint, pk=sprint_id, tenant=tenant)
            task.sprint = target_sprint
            task.save(update_fields=["sprint", "updated_at"])
            write_audit_log(
                request.user,
                task,
                "update",
                {"sprint_id": target_sprint.pk if target_sprint else None},
            )
            messages.success(
                request,
                f"Task {task.number} moved to {target_sprint.name if target_sprint else 'Backlog'}."
            )
        elif action == "update_points":
            raw_pts = request.POST.get("story_points", "").strip()
            pts = int(raw_pts) if raw_pts.isdigit() else None
            task.story_points = pts
            task.save(update_fields=["story_points", "updated_at"])
            write_audit_log(request.user, task, "update", {"story_points": pts})
            messages.success(request, f"Updated story points for {task.number} to {pts or 0}.")
        elif action == "assign_epic":
            epic_id = as_db_int(request.POST.get("epic_id"))
            target_epic = None
            if epic_id:
                target_epic = get_object_or_404(ProjectEpic, pk=epic_id, tenant=tenant)
            task.epic = target_epic
            task.save(update_fields=["epic", "updated_at"])
            write_audit_log(
                request.user,
                task,
                "update",
                {"epic_id": target_epic.pk if target_epic else None},
            )
            messages.success(
                request,
                f"Assigned {task.number} to epic {target_epic.name if target_epic else 'None'}."
            )

        redirect_url = request.path
        if selected_project:
            redirect_url += f"?project={selected_project.pk}"
        return redirect(redirect_url)

    backlog_tasks_qs = (
        ProjectTask.objects.filter(tenant=tenant, sprint__isnull=True)
        .select_related("project", "epic", "release", "assignee", "owner")
        .order_by("sequence", "-created_at")
    )
    active_sprints_qs = (
        Sprint.objects.filter(tenant=tenant, status="active")
        .select_related("project", "scrum_master")
        .order_by("end_date")
    )
    future_sprints_qs = (
        Sprint.objects.filter(tenant=tenant, status="planning")
        .select_related("project", "scrum_master")
        .order_by("start_date")
    )
    epics_qs = ProjectEpic.objects.filter(tenant=tenant).order_by("name")

    if selected_project:
        backlog_tasks_qs = backlog_tasks_qs.filter(project=selected_project)
        active_sprints_qs = active_sprints_qs.filter(project=selected_project)
        future_sprints_qs = future_sprints_qs.filter(project=selected_project)
        epics_qs = epics_qs.filter(project=selected_project)

    total_backlog_points = sum((t.story_points or 0) for t in backlog_tasks_qs)

    context = {
        "backlog_tasks": backlog_tasks_qs,
        "active_sprints": active_sprints_qs,
        "future_sprints": future_sprints_qs,
        "epics": epics_qs,
        "projects": projects,
        "selected_project": selected_project,
        "total_backlog_points": total_backlog_points,
    }
    return render(request, "projects/agile/backlog.html", context)
