"""Projects 7.2 — TaskDependency views: the dependency register.

A plain CRUD register (bullet 2's page). The network itself is read from a task's detail page
(predecessors/successors) and drawn on the WBS tree's critical-chain flag; this register is
where a dependency is created, audited and removed.
"""
from apps.projects.forms import TaskDependencyForm
from apps.projects.models import TaskDependency
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects


@login_required
def dep_list(request):
    qs = (TaskDependency.objects.filter(tenant=request.tenant)
          .select_related("predecessor__project", "successor"))
    return crud_list(
        request, qs, "projects/planning/taskdependency/list.html",
        search_fields=["number", "note", "predecessor__name", "successor__name"],
        filters=[("project", "predecessor__project_id", True),
                 ("link_type", "link_type", False)],
        extra_context={
            "link_type_choices": TaskDependency.LINK_TYPE_CHOICES,
            "projects": projects(request.tenant),
        },
    )


@login_required
def dep_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = TaskDependencyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Dependency {obj.number} created.")
            return redirect("projects:dep_detail", pk=obj.pk)
    else:
        form = TaskDependencyForm(tenant=request.tenant,
                                  initial={"predecessor": request.GET.get("predecessor", ""),
                                           "successor": request.GET.get("successor", "")})
    return render(request, "projects/planning/taskdependency/form.html",
                  {"form": form, "is_edit": False})


@login_required
def dep_detail(request, pk):
    obj = get_object_or_404(
        TaskDependency.objects.select_related("predecessor__project", "predecessor", "successor"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/planning/taskdependency/detail.html", {"obj": obj})


@login_required
def dep_edit(request, pk):
    return crud_edit(
        request, model=TaskDependency, pk=pk, form_class=TaskDependencyForm,
        template="projects/planning/taskdependency/form.html", success_url="projects:dep_list")


@login_required
@require_POST
def dep_delete(request, pk):
    return crud_delete(request, model=TaskDependency, pk=pk,
                       success_url="projects:dep_list")
