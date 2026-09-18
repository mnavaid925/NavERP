"""Projects 7.13 Agile & Scrum Management — Sprint Execution & Daily Standup Board.

Realizes NavERP 7.13 bullet 2:
- Sprint Execution & Daily Standups (burndown charts, impediment tracking, standup note capture)
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.projects.models.AgileScrumManagement.SprintImpediments import SprintImpediment
from apps.projects.models.AgileScrumManagement.Sprints import Sprint
from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask


@login_required
def sprint_execution(request):
    """Execution dashboard showing Kanban task board, standup notes, impediments, and burndown."""
    tenant = request.tenant

    sprints = (
        Sprint.objects.filter(tenant=tenant)
        .select_related("project", "scrum_master")
        .order_by("-start_date", "-created_at")
    )

    sprint_id = as_db_int(request.GET.get("sprint"))
    active_sprint = None
    if sprint_id:
        active_sprint = sprints.filter(pk=sprint_id).first()

    if not active_sprint:
        # Default to first active sprint, or first planning/completed
        active_sprint = sprints.filter(status="active").first() or sprints.first()

    if request.method == "POST" and active_sprint:
        action = request.POST.get("action")
        if action == "save_standup":
            notes = request.POST.get("standup_notes", "").strip()
            active_sprint.standup_notes = notes
            active_sprint.save(update_fields=["standup_notes", "updated_at"])
            write_audit_log(request.user, active_sprint, "update", {"standup_notes": "updated"})
            messages.success(request, "Daily standup notes updated successfully.")
        elif action == "update_task_status":
            task_id = as_db_int(request.POST.get("task_id"))
            new_status = request.POST.get("new_status")
            task = get_object_or_404(ProjectTask, pk=task_id, tenant=tenant, sprint=active_sprint)
            if new_status in dict(ProjectTask.STATUS_CHOICES):
                task.status = new_status
                if new_status == "done":
                    task.percent_complete = 100
                elif new_status == "in_progress" and task.percent_complete == 0:
                    task.percent_complete = 25
                task.save(update_fields=["status", "percent_complete", "updated_at"])
                write_audit_log(request.user, task, "update", {"status": new_status})
                messages.success(request, f"Task {task.number} moved to {task.get_status_display()}.")
        elif action == "quick_impediment":
            title = request.POST.get("title", "").strip()
            severity = request.POST.get("severity", "medium")
            desc = request.POST.get("description", "").strip() or title
            if title:
                imp = SprintImpediment.objects.create(
                    tenant=tenant,
                    sprint=active_sprint,
                    title=title,
                    description=desc,
                    severity=severity,
                    status="open",
                    raised_by=request.user,
                )
                write_audit_log(request.user, imp, "create", {"title": title, "severity": severity})
                messages.success(request, f"Impediment {imp.number} logged for sprint.")

        return redirect(f"{request.path}?sprint={active_sprint.pk}")

    todo_tasks = []
    in_progress_tasks = []
    done_tasks = []
    impediments = []
    standup_notes = ""
    burndown_data = {
        "total_points": 0,
        "committed_points": 0,
        "completed_points": 0,
        "remaining_points": 0,
        "completion_rate": 0,
        "day_points": [],
    }

    if active_sprint:
        standup_notes = active_sprint.standup_notes
        tasks_qs = active_sprint.tasks.select_related("assignee", "epic").order_by("sequence", "id")
        for t in tasks_qs:
            if t.status in ("done", "closed"):
                done_tasks.append(t)
            elif t.status in ("in_progress", "active"):
                in_progress_tasks.append(t)
            else:
                todo_tasks.append(t)

        impediments = active_sprint.impediments.select_related("owner").order_by("-created_at")

        total_pts = active_sprint.total_points
        comp_pts = active_sprint.completed_points
        rem_pts = active_sprint.remaining_points
        comm_pts = active_sprint.committed_points or total_pts

        burndown_data = {
            "total_points": total_pts,
            "committed_points": comm_pts,
            "completed_points": comp_pts,
            "remaining_points": rem_pts,
            "completion_rate": active_sprint.completion_rate,
        }

    context = {
        "active_sprint": active_sprint,
        "sprints": sprints,
        "todo_tasks": todo_tasks,
        "in_progress_tasks": in_progress_tasks,
        "done_tasks": done_tasks,
        "impediments": impediments,
        "burndown_data": burndown_data,
        "standup_notes": standup_notes,
    }
    return render(request, "projects/agile/execution.html", context)
