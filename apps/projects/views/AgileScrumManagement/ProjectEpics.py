"""Projects 7.13 Agile & Scrum Management — ProjectEpic views.
"""
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int
from apps.projects.forms.AgileScrumManagement.ProjectEpics import ProjectEpicForm
from apps.projects.models.AgileScrumManagement.ProjectEpics import ProjectEpic
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import *  # noqa: F401,F403


@login_required
def epc_list(request):
    qs = (
        ProjectEpic.objects.filter(tenant=request.tenant)
        .select_related("project", "owner")
        .prefetch_related("tasks")
    )
    project_id = as_db_int(request.GET.get("project"))
    if project_id:
        qs = qs.filter(project_id=project_id)

    projects = Project.objects.filter(tenant=request.tenant).order_by("name")

    return crud_list(
        request,
        qs,
        "projects/agile/epic/list.html",
        search_fields=["name", "summary"],
        filters=[
            ("status", "status", False),
        ],
        extra_context={
            "epics": qs,
            "status_choices": ProjectEpic.STATUS_CHOICES,
            "projects": projects,
            "selected_project_id": project_id,
            "total_count": qs.count(),
        },
    )


@login_required
def epc_create(request):
    return crud_create(
        request,
        form_class=ProjectEpicForm,
        template="projects/agile/epic/form.html",
        success_url="projects:epc_list",
    )


@login_required
def epc_detail(request, pk):
    epic = get_object_or_404(
        ProjectEpic.objects.select_related("project", "owner"),
        pk=pk,
        tenant=request.tenant,
    )
    tasks = epic.tasks.select_related("assignee", "sprint").order_by("sequence", "id")

    return render(
        request,
        "projects/agile/epic/detail.html",
        {
            "obj": epic,
            "epic": epic,
            "tasks": tasks,
        },
    )


@login_required
def epc_edit(request, pk):
    return crud_edit(
        request,
        model=ProjectEpic,
        pk=pk,
        form_class=ProjectEpicForm,
        template="projects/agile/epic/form.html",
        success_url="projects:epc_list",
    )


@login_required
@require_POST
def epc_delete(request, pk):
    return crud_delete(
        request,
        model=ProjectEpic,
        pk=pk,
        success_url="projects:epc_list",
    )
