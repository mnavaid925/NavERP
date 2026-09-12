"""Projects 7.8 — the Priority & Urgency lens (bullet 2; computed on read; no model; GET-only).

Bullet 2 is two frameworks over the same scoped task list, neither of them a stored score:

* **MoSCoW** — the four declared classifications in order, PLUS a trailing ``unclassified``
  group: ``moscow`` has no default on purpose — unclassified is a STATE, not a value, so it
  gets its own bucket instead of being silently folded into one of the four.
* **Eisenhower** — the 2×2 grid, bucketed on read from the two boolean flags through the
  model's own ``eisenhower_quadrant`` property, so the page can never disagree with the model.

The **work queue** is the one actionable list: live tasks (``planned``/``in_progress``) that
are overdue, blocked or high/critical priority, ordered overdue-first and capped at
``_WORK_QUEUE_CAP`` — the "what do I do next" lens, not a second register.

Priority is whatever each row attests — there is no computed priority score here (that is
7.19's framework work), and nothing on this page is stored. ``?project=`` and ``?assignee=``
are the page's only parameters (the three computed pages share the parse): through
``as_db_int``, resolved against tenant-scoped querysets — a junk or out-of-tenant id degrades
to ``None``, never a 500. The manual-block half of the blocking lens is computed in bulk (one
``Prefetch`` of ACTIVE blocks) because ``is_manually_blocked``'s
``blocks.filter(...).exists()`` re-queries per row even over a prefetch cache; the dependency
half reads ``is_dependency_blocked`` straight off the prefetched links (see ``TaskBoard.py``
for the same shape).
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

#: Verbatim re-declaration of the board's rank map (the ``_helpers`` single-consumer rule —
#: a third consumer moves it to ``_helpers``): every group's rows read critical-first.
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

#: The work queue's cap (the contract's pin) — the queue is a lens, not a second register.
_WORK_QUEUE_CAP = 25

#: Working-set cap for the page (the 7.5/7.6 computed-page idiom — a partial lens beats an
#: unparameterised whole-table materialisation in the request thread).
_REGISTER_CAP = 2000

#: The Eisenhower grid in fixed order with its pinned badge classes (colour names only, L33 —
#: verified at ``theme.css:286-291``). The keys are ``eisenhower_quadrant``'s exact values.
_QUADRANTS = [
    ("do_first", "Do First", "badge-red"),
    ("schedule", "Schedule", "badge-info"),
    ("delegate", "Delegate", "badge-amber"),
    ("eliminate", "Eliminate", "badge-slate"),
]


def _priority_sort_key(task):
    """Every group's row order: priority rank, then ``planned_start`` with nulls LAST, then
    ``-id`` as the deterministic tiebreak (the board's Wrike-style order)."""
    return (
        _PRIORITY_RANK.get(task.priority, len(_PRIORITY_RANK)),
        (0, task.planned_start) if task.planned_start else (1,),
        -task.pk,
    )


def _group_moscow(tasks):
    """The MoSCoW groups in declared order plus the trailing ``unclassified`` group.

    Group labels come from the model's own ``MOSCOW_CHOICES`` (a second inline copy could
    drift from the register without any error — the ``risk_monitoring`` band-vocabulary
    ruling); each group's tasks are ordered priority-rank → ``planned_start`` (nulls last).
    """
    groups = [{"value": value, "label": label, "tasks": [], "count": 0}
              for value, label in ProjectTask.MOSCOW_CHOICES]
    groups.append({"value": None, "label": "Unclassified", "tasks": [], "count": 0})
    by_value = {group["value"]: group for group in groups}
    for task in tasks:
        by_value.get(task.moscow, by_value[None])["tasks"].append(task)
    for group in groups:
        group["tasks"].sort(key=_priority_sort_key)
        group["count"] = len(group["tasks"])
    return groups


def _bucket_quadrants(tasks):
    """The 2×2 in fixed order, bucketed through the model's ``eisenhower_quadrant``."""
    buckets = {key: [] for key, _, _ in _QUADRANTS}
    for task in tasks:
        buckets[task.eisenhower_quadrant].append(task)
    quadrants = []
    for key, label, badge in _QUADRANTS:
        bucket = buckets[key]
        bucket.sort(key=_priority_sort_key)
        quadrants.append({
            "key": key,
            "label": label,
            "tasks": bucket,
            "count": len(bucket),
            "badge": badge,
        })
    return quadrants


def _work_queue(tasks, blocked_ids):
    """The capped work queue — live tasks that are overdue, blocked or high/critical.

    ``blocked_ids`` is the set of task pks with an open manual block, computed in bulk by the
    view (the ``is_manually_blocked`` property's ``.filter().exists()`` bypasses the prefetch
    cache); the dependency half reads ``is_dependency_blocked`` off the prefetched links, so
    the test is exactly ``is_blocked``'s verdict without its per-row queries. Ordered
    overdue-first → priority rank → ``planned_start`` (nulls last), capped at
    ``_WORK_QUEUE_CAP``.
    """
    queue = []
    for task in tasks:
        if task.status not in ("planned", "in_progress"):
            continue
        if not (task.is_overdue or task.is_dependency_blocked
                or task.pk in blocked_ids or task.priority in ("high", "critical")):
            continue
        queue.append(task)
    queue.sort(key=lambda task: (0 if task.is_overdue else 1, _priority_sort_key(task)))
    return queue[:_WORK_QUEUE_CAP]


@login_required
def task_priority(request):
    """Bullet 2's lens — the MoSCoW groups, the Eisenhower grid, the capped work queue and
    the four execution counts, all computed from one materialized, tenant-scoped task list.
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

    tasks = list(qs[:_REGISTER_CAP])
    blocked_ids = {task.pk for task in tasks if task.active_blocks}

    moscow_groups = _group_moscow(tasks)
    quadrants = _bucket_quadrants(tasks)
    work_queue = _work_queue(tasks, blocked_ids)

    # The four counts over the materialized list (the contract's parenthetical): blocked and
    # overdue are properties, so no DB aggregate can produce them — and the other two come
    # from the same pass so all four figures describe the same snapshot.
    counts = {"overdue": 0, "blocked": 0, "unassigned": 0, "in_progress": 0}
    for task in tasks:
        if task.is_overdue:
            counts["overdue"] += 1
        if task.is_dependency_blocked or task.active_blocks:
            counts["blocked"] += 1
        if task.status == "in_progress":
            counts["in_progress"] += 1
        if task.status in ("planned", "in_progress") and task.assignee_id is None:
            counts["unassigned"] += 1

    return render(request, "projects/taskwork/task_priority.html", {
        "projects": project_qs,
        "project": project,
        "assignees": assignee_qs,
        "assignee": assignee,
        "moscow_groups": moscow_groups,
        "quadrants": quadrants,
        "work_queue": work_queue,
        "counts": counts,
    })
