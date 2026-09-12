"""Projects 7.8 — the Task Board (bullet 3, "Kanban & Scrum Boards"; computed on read; no model).

The columns ARE ``ProjectTask.STATUS_CHOICES`` in declared order (Ruling 4 — no workflow
engine, no column-config table): one dict per status, tasks bucketed in Python from ONE
materialized queryset (the ``crmproject_board`` idiom — bucket on read, never re-query per
column). Every card's execution state — blocked, overdue, ready — is a derived property or a
figure computed here on read; nothing on this page is stored.

``WIP_LIMITS`` is the 7.19 hook (Ruling 4): deliberately EMPTY today — the limit VALUES are
configuration that sub-module does not own yet — so ``over_limit`` is always ``False``. The
comparison is coded anyway: filling the dict is the whole 7.19 change, and the counts already
render.

Deliverable nodes are summary cards, not work rows: they carry no verb buttons and render the
rollup over their descendant work packages (the same effort-weighted progress the Gantt page
computes for its deliverable bars — the two walkers are siblings on purpose, and a third
consumer is the trigger to move one into ``_helpers``).

``?project=`` scopes to one project (``None`` → the whole workspace); ``?assignee=`` is the
"my tasks" lens. Both are parsed through ``as_db_int`` and resolved against tenant-scoped
querysets — a junk or out-of-tenant id degrades to ``None``, never a 500. No other query
parameter is parsed (the contract pins exactly these two).

Query discipline (the 7.5/7.6 computed-board idiom): the board list is materialized ONCE under
a working-set cap, with ``select_related`` for every card's FK render and two prefetches — the
predecessor links the blocking lens reads (``is_dependency_blocked`` then runs off the prefetch
cache) and the ACTIVE blocks. The manual-block half of ``is_blocked`` is computed in bulk
instead of through ``is_manually_blocked`` because that property's
``blocks.filter(...).exists()`` re-queries per row even over a prefetch cache (Django's related
manager returns the cache only to plain ``.all()`` — a ``.filter()`` chains a fresh clone); the
bulk prefetch runs exactly the property's lookup (``unblocked_at__isnull=True``, the
``tbk_tnt_unblocked_idx`` one), so the verdict is identical, at one query for the whole board.
"""
from django.contrib.auth import get_user_model
from django.db.models import Prefetch

from apps.core.crud import as_db_int
from apps.projects.models import Project, ProjectTask
# Direct sub-module import: the models package re-export lands in the Integrate step.
from apps.projects.models.TaskWorkManagement.TaskBlocks import TaskBlock
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render
from apps.projects.views._helpers import owners, projects as project_choices

#: Status value -> its WIP limit. EMPTY BY DESIGN until 7.19 ships the limit configuration
#: (Ruling 4): counts render now, ``over_limit`` stays False, and the comparison in the view
#: is already coded — filling this dict is the whole change.
WIP_LIMITS: dict = {}

#: Working-set cap for the board (the 7.5/7.6 computed-page idiom). A task table large enough
#: to hit it makes the board and its counts a partial view — but an unparameterised
#: whole-table materialisation in the request thread is the worse failure.
_BOARD_CAP = 2000

#: Priority rank for the within-column order (critical -> high -> medium -> low — Wrike's
#: priority-default sort). Declared locally; ``TaskPriority.py`` re-declares it verbatim (the
#: ``_helpers`` single-consumer rule — a third consumer moves it to ``_helpers``).
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _board_sort_key(task):
    """Within-column order: priority rank, then ``planned_start`` with nulls LAST (the
    undated sink to the bottom — they never jump the dated queue), then ``-id`` (newest
    first among identical keys)."""
    return (
        _PRIORITY_RANK.get(task.priority, len(_PRIORITY_RANK)),
        (0, task.planned_start) if task.planned_start else (1,),
        -task.pk,
    )


def _queue_sort_key(task):
    """Ready-queue order: ``planned_start`` (nulls last), then ``id``."""
    return ((0, task.planned_start) if task.planned_start else (1,), task.pk)


def _deliverable_rollups(tasks):
    """Per-deliverable rollup figures over the materialized board list.

    Returns ``{deliverable_pk: {"wp_count": int, "progress_pct": float|None}}`` where
    ``progress_pct`` is the effort-weighted rollup over the descendant work packages —
    ``Σ(percent_complete × effort_hours or 0) / Σ(effort_hours or 0)``, falling back to the
    unweighted descendant mean when ``Σeffort`` is 0 and ``None`` with no descendants — the
    same figure ``GanttTimeline.py`` computes for its deliverable bars (both walkers live in
    their consumer's module because the contract freezes ``_helpers`` for this pass).

    Children are matched by ``parent_id`` INSIDE the materialized list, so a descendant
    beyond the cap simply does not contribute — a partial rollup is the documented cost of
    capping. Work packages aggregate their OWN figures (the ``_decorate_wbs`` semantics);
    deliverables aggregate nothing of their own. The walk is ITERATIVE over explicit frames
    (the ``_decorate_wbs`` ruling: a member-built parent chain must not be able to
    RecursionError the request); a cycle edge contributes nothing, so every walk terminates.
    """
    children_of = {}
    for node in tasks:
        children_of.setdefault(node.parent_id, []).append(node)

    # finished: pk -> (wp_count, effort_total, weighted_total, plain_total); a frame is
    # [node, child iterator, wp_count, effort_total, weighted_total, plain_total].
    finished = {}
    rollups = {}
    for seed in tasks:
        if seed.pk in finished:
            continue
        stack = [[seed, iter(children_of.get(seed.pk, ())), 0, 0.0, 0.0, 0.0]]
        in_progress = {seed.pk}
        while stack:
            frame = stack[-1]
            child = next(frame[1], None)
            if child is not None:
                if child.pk in finished:
                    agg = finished[child.pk]
                    frame[2] += agg[0]
                    frame[3] += agg[1]
                    frame[4] += agg[2]
                    frame[5] += agg[3]
                elif child.pk not in in_progress:
                    in_progress.add(child.pk)
                    stack.append(
                        [child, iter(children_of.get(child.pk, ())), 0, 0.0, 0.0, 0.0])
                continue
            stack.pop()
            in_progress.discard(frame[0].pk)
            node = frame[0]
            if node.node_type == "work_package":
                pct = float(node.percent_complete or 0)
                effort = float(node.effort_hours or 0)
                agg = (1, effort, pct * effort, pct)
            else:
                agg = (frame[2], frame[3], frame[4], frame[5])
                rollups[node.pk] = {
                    "wp_count": agg[0],
                    "progress_pct": (round(agg[2] / agg[1], 1) if agg[1] > 0
                                     else round(agg[3] / agg[0], 1) if agg[0] else None),
                }
            finished[node.pk] = agg
            if stack:  # fold this subtree into the parent's accumulator
                parent = stack[-1]
                parent[2] += agg[0]
                parent[3] += agg[1]
                parent[4] += agg[2]
                parent[5] += agg[3]
    return rollups


@login_required
def task_board(request):
    """Bullet 3's board — the four status columns, the ready queue and the execution counts,
    all computed from one materialized, tenant-scoped task list.

    Columns are built in ``STATUS_CHOICES`` declared order; the ready queue is the planned
    slice whose predecessors are all settled and that carries no open block — the tasks the
    Start verb can actually take right now.
    """
    tenant = request.tenant
    project_qs = project_choices(tenant)
    assignee_qs = owners(tenant)

    project = None
    project_id = as_db_int(request.GET.get("project"))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()

    assignee = None
    assignee_id = as_db_int(request.GET.get("assignee"))
    if assignee_id is not None:
        assignee = get_user_model().objects.filter(tenant=tenant, pk=assignee_id).first()

    qs = (ProjectTask.objects.filter(tenant=tenant)
          .select_related("project", "assignee")
          .prefetch_related(
              "predecessor_links__predecessor",
              Prefetch("blocks",
                       queryset=TaskBlock.objects.filter(
                           tenant=tenant, unblocked_at__isnull=True),
                       to_attr="active_blocks")))
    if project is not None:
        qs = qs.filter(project=project)
    if assignee is not None:
        qs = qs.filter(assignee=assignee)

    board_tasks = list(qs[:_BOARD_CAP])
    total_count = len(board_tasks) if len(board_tasks) < _BOARD_CAP else qs.count()

    by_status = {value: [] for value, _ in ProjectTask.STATUS_CHOICES}
    blocked_count = overdue_count = 0
    ready_queue = []
    for task in board_tasks:
        by_status.setdefault(task.status, []).append(task)
        # is_blocked's two halves: the dependency verdict reads the prefetched links (the
        # property itself is cache-safe), the manual verdict reads the bulk-prefetched
        # active blocks — identical to ``is_manually_blocked``'s lookup, without its
        # per-row query.
        if task.is_dependency_blocked or task.active_blocks:
            blocked_count += 1
        if task.is_overdue:
            overdue_count += 1
        if (task.status == "planned" and task.predecessor_links.all()
                and not task.is_dependency_blocked and not task.active_blocks):
            ready_queue.append(task)

    # Deliverable summary cards: the rollup figures hang off the instance in memory only
    # (the ``_decorate_wbs`` in-memory-decoration idiom) — never a stored column.
    rollups = _deliverable_rollups(board_tasks)
    for task in board_tasks:
        if task.node_type == "deliverable":
            task.board_rollup = rollups.get(task.pk, {"wp_count": 0, "progress_pct": None})

    columns = []
    for value, label in ProjectTask.STATUS_CHOICES:
        column_tasks = by_status.get(value, [])
        column_tasks.sort(key=_board_sort_key)
        limit = WIP_LIMITS.get(value)
        columns.append({
            "value": value,
            "label": label,
            "tasks": column_tasks,
            "count": len(column_tasks),
            # The 7.19 hook: no WIP_LIMITS entry means no limit — always False today; the
            # comparison is the whole code 7.19 needs once the dict is filled.
            "over_limit": limit is not None and len(column_tasks) > limit,
        })

    ready_queue.sort(key=_queue_sort_key)

    return render(request, "projects/taskwork/task_board.html", {
        "projects": project_qs,
        "project": project,
        "assignees": assignee_qs,
        "assignee": assignee,
        "columns": columns,
        "ready_queue": ready_queue,
        "total_count": total_count,
        "blocked_count": blocked_count,
        "overdue_count": overdue_count,
    })
