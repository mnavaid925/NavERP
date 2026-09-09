"""Projects 7.2 — ProjectTask views: the WBS tree and the task register.

``tsk_tree`` is bullet 1's hero page (Work Breakdown Structure): the project's whole tree is
prefetched once, then every node is decorated IN PYTHON — hierarchical WBS code, critical-chain
flag, and the post-order date/effort rollup a deliverable displays. Nothing decorated is stored;
the register (``tsk_list``) is the flat lens on the same rows.
"""
from apps.core.crud import as_db_int
from apps.projects.forms import TaskForm
from apps.projects.models import ProjectTask
from apps.projects.models._base import ZERO, q2
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import critical_path_ids, projects


def _decorate_wbs(project):
    """Prefetch the project's WBS once, decorate each node, return ``(roots, critical_ids)``.

    Instance attributes set here (in-memory only): ``wbs_code`` ("1.2.3" — derived from tree
    position, never stored), ``is_critical`` (bullet 2's chain), ``kids`` (the decorated child
    nodes, for the recursive include), and the effective window/effort
    — own values on a work package, the post-order subtree rollup on a deliverable — as
    ``rollup_start`` / ``rollup_end`` / ``rollup_effort_hours`` / ``rollup_count``. The ``rolled``
    set is cycle insurance: a cycle in the data (not creatable through the forms) costs a skipped
    node with unset rollups, never an infinite recursion — and every read of a child's rollup
    tolerates it having never been set.
    """
    # ONE query for the whole tree (the tree template renders no owner column, so nothing is
    # select_related). Children are hung on their parent as ``node.kids`` — the DECORATED
    # instances — rather than read through ``node.children.all``: prefetch_related would fetch
    # the children a second time as DIFFERENT Python objects, and the template would render
    # undecorated rows (no wbs_code, no rollup, no critical flag).
    nodes = list(project.tasks.order_by("sequence", "id"))
    children_of = {}
    for node in nodes:
        children_of.setdefault(node.parent_id, []).append(node)
    critical = critical_path_ids(project)
    rolled = set()

    def walk(node, code):
        if node.pk in rolled:
            return
        rolled.add(node.pk)
        node.wbs_code = code
        node.is_critical = node.pk in critical
        node.kids = kids = children_of.get(node.pk, [])
        for i, child in enumerate(kids, start=1):
            walk(child, f"{code}.{i}")
        if node.node_type == "work_package":
            node.rollup_start = node.planned_start
            node.rollup_end = node.planned_end
            node.rollup_effort_hours = node.effort_hours or ZERO
            node.rollup_count = 1
        else:
            starts = [s for s in (getattr(k, "rollup_start", None) for k in kids) if s]
            ends = [e for e in (getattr(k, "rollup_end", None) for k in kids) if e]
            node.rollup_start = min(starts) if starts else None
            node.rollup_end = max(ends) if ends else None
            node.rollup_effort_hours = q2(sum(
                (getattr(k, "rollup_effort_hours", None) or ZERO for k in kids), ZERO))
            node.rollup_count = sum(getattr(k, "rollup_count", 0) or 0 for k in kids)

    roots = children_of.get(None, [])
    for i, root in enumerate(roots, start=1):
        walk(root, str(i))
    return roots, critical


@login_required
def tsk_list(request):
    qs = (ProjectTask.objects.filter(tenant=request.tenant)
          .select_related("project", "parent", "owner"))
    return crud_list(
        request, qs, "projects/planning/task/list.html",
        search_fields=["name", "number", "description"],
        filters=[("project", "project_id", True),
                 ("status", "status", False),
                 ("node_type", "node_type", False),
                 ("estimation_method", "estimation_method", False)],
        extra_context={
            "status_choices": ProjectTask.STATUS_CHOICES,
            "node_type_choices": ProjectTask.NODE_TYPE_CHOICES,
            "estimation_method_choices": ProjectTask.ESTIMATION_CHOICES,
            "projects": projects(request.tenant),
        },
    )


@login_required
def tsk_tree(request):
    tenant_projects = projects(request.tenant)
    project_id = as_db_int(request.GET.get("project"))
    project = None
    if project_id is not None:
        project = tenant_projects.filter(pk=project_id).first()
    if project is None:
        project = tenant_projects.first()
    roots, critical_ids = [], set()
    if project is not None:
        roots, critical_ids = _decorate_wbs(project)
    return render(request, "projects/planning/task/tree.html", {
        "project": project,
        "projects": tenant_projects,
        "roots": roots,
        "tree_max_depth": 5,
        "critical_ids": critical_ids,
    })


@login_required
def tsk_create(request):
    # FIRST LINE, not inside `if form.is_valid()` — the pko_create shape: a tenant-less user must
    # never reach a form whose FK dropdowns would otherwise render unscoped.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = TaskForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Task {obj.number} created.")
            return redirect("projects:tsk_detail", pk=obj.pk)
    else:
        form = TaskForm(tenant=request.tenant,
                        initial={"project": request.GET.get("project", "")})
    return render(request, "projects/planning/task/form.html",
                  {"form": form, "is_edit": False})


@login_required
def tsk_detail(request, pk):
    obj = get_object_or_404(
        ProjectTask.objects.select_related("project", "parent", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/planning/task/detail.html", {
        "obj": obj,
        "child_tasks": obj.children.select_related("owner").order_by("sequence", "id")[:50],
        # Links where THIS task is the predecessor (its successors) and where it is the
        # successor (its predecessors) — the dependency network from the task's point of view.
        "predecessor_links": obj.predecessor_links.select_related(
            "predecessor", "predecessor__project")[:50],
        "successor_links": obj.successor_links.select_related(
            "successor", "successor__project")[:50],
    })


@login_required
def tsk_edit(request, pk):
    return crud_edit(
        request, model=ProjectTask, pk=pk, form_class=TaskForm,
        template="projects/planning/task/form.html", success_url="projects:tsk_list")


@login_required
@require_POST
def tsk_delete(request, pk):
    return crud_delete(request, model=ProjectTask, pk=pk, success_url="projects:tsk_list")
