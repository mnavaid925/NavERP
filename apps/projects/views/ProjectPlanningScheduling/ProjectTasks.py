"""Projects 7.2 — ProjectTask views: the WBS tree and the task register.

``tsk_tree`` is bullet 1's hero page (Work Breakdown Structure): the project's whole tree is
prefetched once, then every node is decorated IN PYTHON — hierarchical WBS code, critical-chain
flag, and the post-order date/effort rollup a deliverable displays. Nothing decorated is stored;
the register (``tsk_list``) is the flat lens on the same rows.
"""
from django.db import transaction
from django.db.models import Prefetch

from apps.core.crud import as_db_int
from apps.projects.forms import TaskForm
# 7.8 surgical edit (context additions only — no behavior change): the task-detail page embeds
# the blocks panel, whose two verb bodies POST to the POST-only task verbs. Direct sub-module
# import — the forms package re-exports land in the Integrate step.
from apps.projects.forms.TaskWorkManagement.TaskBlocks import TaskBlockForm, TaskUnblockForm
from apps.projects.models import ProjectTask, TaskBlock, TaskChecklistItem, TaskDependency
from apps.projects.models._base import ZERO, q2
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import critical_path_ids, owners, projects


#: Hard ceiling on WBS depth the decoration walk will traverse. The template's own recursion is
#: capped at ``tree_max_depth`` (5), so this only backstops pathological parent chains (a member
#: can chain parents far deeper than anything renderable) — nodes beyond it keep ``wbs_code``
#: unset and are simply absent from the rendered tree instead of risking unbounded work.
WBS_MAX_DEPTH = 20


def _decorate_wbs(project):
    """Prefetch the project's WBS once, decorate each node, return ``(roots, critical_ids)``.

    Instance attributes set here (in-memory only): ``wbs_code`` ("1.2.3" — derived from tree
    position, never stored), ``is_critical`` (bullet 2's chain), ``kids`` (the decorated child
    nodes, for the recursive include), and the effective window/effort
    — own values on a work package, the post-order subtree rollup on a deliverable — as
    ``rollup_start`` / ``rollup_end`` / ``rollup_effort_hours`` / ``rollup_count``.

    The walk is an ITERATIVE post-order over an explicit stack (the template recursion is capped,
    so the Python walk must be too — a member-built parent chain cannot blow the interpreter
    stack): nodes deeper than ``WBS_MAX_DEPTH`` are never decorated and never hung into a
    ``kids`` chain, so they are gracefully absent from the tree.

    The ``rolled`` set is cycle insurance, and its behavior is exactly this: a cycle REACHABLE
    from a root decorates each of its nodes once, but the cycle's ``kids`` links still point at
    each other, so the template re-renders the duplicated subtree until the template's own
    ``tree_max_depth`` cap stops it; a cycle DISCONNECTED from every root (no root path into it)
    is never walked at all and is absent from the tree. Either way the Python walk terminates and
    every read of a child's rollup tolerates it having never been set.
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

    def rollup(node):
        """Post-order decoration: own window/effort on a work package, subtree rollup on a
        deliverable. Child rollups are always set here EXCEPT across a cycle edge, where the
        ``getattr`` defaults keep the parent's rollup well-defined anyway."""
        kids = node.kids
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
    # LIFO discipline: push each level's children REVERSED (with their codes) so they pop in
    # list order and every parent's finalize entry pops after its children's — a true post-order.
    stack = [(root, str(i), 1, False)
             for i, root in reversed(list(enumerate(roots, start=1)))]
    while stack:
        node, code, depth, finalize = stack.pop()
        if finalize:
            rollup(node)
            continue
        if node.pk in rolled:  # cycle re-entry: this node's subtree is already being processed
            continue
        rolled.add(node.pk)
        node.wbs_code = code
        node.is_critical = node.pk in critical
        node.kids = children_of.get(node.pk, []) if depth < WBS_MAX_DEPTH else []
        stack.append((node, code, depth, True))
        for i, child in reversed(list(enumerate(node.kids, start=1))):
            stack.append((child, f"{code}.{i}", depth + 1, False))
    return roots, critical


@login_required
def tsk_list(request):
    qs = (ProjectTask.objects.filter(tenant=request.tenant)
          .select_related("project", "owner"))
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
            # 7.8 bulk bar (context additions only): the picker dropdowns are tenant-scoped —
            # statuses/priorities from the model's CHOICES, assignees from this workspace's users.
            "priority_choices": ProjectTask.PRIORITY_CHOICES,
            "assignee_choices": owners(request.tenant),
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
            with transaction.atomic():
                obj.save()
                form.save_custom_values(obj, updated_by=request.user)
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
    # The 7.8 panels are prefetched ONCE here so no panel materializes a manager of its own:
    # the checklist trail (+ the done-by user), the block evidence trail (+ both stamp users),
    # and the dependency links (+ the counterpart task) — the derived blocking verdicts then
    # read straight off the prefetch caches.
    obj = get_object_or_404(
        ProjectTask.objects.select_related("project", "parent", "owner").prefetch_related(
            Prefetch("checklist_items",
                     queryset=TaskChecklistItem.objects.select_related("done_by")),
            Prefetch("blocks",
                     queryset=TaskBlock.objects.select_related("blocked_by", "unblocked_by")),
            Prefetch("predecessor_links", queryset=TaskDependency.objects.select_related(
                "predecessor", "predecessor__project")),
            Prefetch("successor_links", queryset=TaskDependency.objects.select_related(
                "successor", "successor__project")),
        ),
        pk=pk, tenant=request.tenant)
    # The manual-block free half, computed once from the prefetched trail (the board's
    # to_attr="active_blocks" idiom — is_manually_blocked's .filter().exists() would bypass
    # the cache and re-query per badge). The dependency free half reads the cached links.
    obj.active_blocks = [block for block in obj.blocks.all() if block.is_active]
    checklist_items = obj.checklist_items.all()
    checklist_progress = (
        int(round(sum(1 for item in checklist_items if item.is_done)
                  / len(checklist_items) * 100))
        if len(checklist_items) else None)
    return render(request, "projects/planning/task/detail.html", {
        "obj": obj,
        "child_tasks": obj.children.select_related("owner").order_by("sequence", "id")[:50],
        # Links where THIS task is the predecessor (its successors) and where it is the
        # successor (its predecessors) — the dependency network from the task's point of view,
        # sliced off the prefetch cache so the page keeps one query path per relation.
        "predecessor_links": obj.predecessor_links.all()[:50],
        "successor_links": obj.successor_links.all()[:50],
        # 7.8: the one checklist progress figure, computed in the view off the prefetched rows
        # (the model property's two COUNTs would bypass the prefetch by construction).
        "checklist_progress": checklist_progress,
        # 7.8: the blocks panel embeds the two verb bodies — raising a blocker and clearing the
        # active one POST to projects:tsk_block / projects:tsk_unblock on this task.
        "block_form": TaskBlockForm(),
        "unblock_form": TaskUnblockForm(),
    })


@login_required
def tsk_edit(request, pk):
    return crud_edit(
        request, model=ProjectTask, pk=pk, form_class=TaskForm,
        template="projects/planning/task/form.html", success_url="projects:tsk_list",
        form_kwargs={"updated_by": request.user})


@login_required
@require_POST
def tsk_delete(request, pk):
    return crud_delete(request, model=ProjectTask, pk=pk, success_url="projects:tsk_list")
