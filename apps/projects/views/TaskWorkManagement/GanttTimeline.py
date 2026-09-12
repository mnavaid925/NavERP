"""Projects 7.8 — the Gantt timeline (bullet 4, "Gantt Charts & Timeline Views"; computed on
read; no model; GET-only).

Bullet 4's page draws the selected project's WBS as CSS bars over a resolved window — **no
chart library** (7.16 owns charts) and **no stored layout**: the bars, the dependency links
table and the finish-to-start date conflicts are recomputed on every request.

**Window resolution (pinned, never a 500).** ``?start=``/``?end=`` bind to the private
``_GanttWindowForm`` — a junk value fails validation and falls through to the default, never a
hand-rolled ``date`` parse that 500s on a URL anyone can type. The default is the task-date
union padded ``_WINDOW_PAD_DAYS`` on each side (each side resolves independently: the union's
earliest start minus the pad, the union's latest end plus the pad — a side with no dates falls
to ``today`` / ``today+30``, the contract's undated default). Clamps: ``end <= start`` →
``end = start + _DEFAULT_SPAN_DAYS``; a span over ``_MAX_SPAN_DAYS`` is clamped to exactly
``start + _MAX_SPAN_DAYS``. ``days`` is INCLUSIVE (``(end - start).days + 1`` — the
``duration_days`` idiom).

**Bars.** One dict per WBS node in TREE order (pre-order over the ``sequence``, ``id``-ordered
sibling lists; ``depth`` 0 = root), computed from the prefetched task list: work packages get
their own dates and ``percent_complete``; deliverables get the min/max descendant window and
the effort-weighted progress rollup over descendant work packages —
``Σ(percent_complete × effort_hours or 0) / Σ(effort_hours or 0)``, falling back to the
unweighted descendant mean when ``Σeffort`` is 0, ``None`` with no descendants (Ruling 5:
computed on read, never stored). ``left_pct``/``width_pct`` are ``None`` for undated nodes
(the template renders the label row without a bar) and are otherwise RAW percentages of the
window — a bar may start before 0% or end past 100% when a task pokes outside the chosen
window; the row track clips it visually while the title carries the true dates. An inverted
date pair cannot go below a one-day bar (the ``critical_path_ids`` duration ruling). The
critical-chain highlight reads ``critical_path_ids`` (``views/_helpers.py`` — reused, nothing
added there); arrows are JS and deferred, so the links render as the table beside the chart.

The walk is ITERATIVE over explicit frames (the ``_decorate_wbs`` ruling: a member-built
parent chain must not be able to RecursionError the request); nodes beyond ``_GANTT_MAX_DEPTH``
and cycle members unreachable as roots are simply absent, exactly like the 7.2 tree page.
"""
from datetime import timedelta

from django import forms

from apps.core.crud import as_db_int
from apps.projects.models import Project, ProjectTask, TaskDependency
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render, timezone
from apps.projects.views._helpers import critical_path_ids, projects as project_choices

#: The default window's pad and clamps (the contract's exact pins).
_WINDOW_PAD_DAYS = 7
_DEFAULT_SPAN_DAYS = 30
_MAX_SPAN_DAYS = 366

#: Depth ceiling for the decoration walk (the 7.2 ``WBS_MAX_DEPTH`` idiom — the template has
#: no recursion to cap here, so this is the only guard against pathological parent chains).
_GANTT_MAX_DEPTH = 20


class _GanttWindowForm(forms.Form):
    """The window adjuster, parsed as a form (L35) so a junk ``?start=abc`` is a validation
    error that falls back to the default — never a 500. Private to this view module on
    purpose: the contract keeps a ``GanttWindowForm`` OUT of the forms package."""

    start = forms.DateField(required=False)
    end = forms.DateField(required=False)


def _resolve_window(start, end, default_start, default_end):
    """Pure window resolution — the contract's exact clamps, asserted in isolation.

    Each side falls to its default independently, then ``end <= start`` stretches the window
    to ``_DEFAULT_SPAN_DAYS`` and a span over ``_MAX_SPAN_DAYS`` is clamped to it. Returns
    ``(start, end, days)`` with ``days`` inclusive.
    """
    start = default_start if start is None else start
    end = default_end if end is None else end
    if end <= start:
        end = start + timedelta(days=_DEFAULT_SPAN_DAYS)
    if (end - start).days > _MAX_SPAN_DAYS:
        end = start + timedelta(days=_MAX_SPAN_DAYS)
    return start, end, (end - start).days + 1


def _merge_subtree(frame, agg):
    """Fold a child subtree's aggregate into its parent's accumulating frame: the subtree
    window's earliest start / latest end and the descendant work-package sums."""
    if agg[0] is not None and (frame[2] is None or agg[0] < frame[2]):
        frame[2] = agg[0]
    if agg[1] is not None and (frame[3] is None or agg[1] > frame[3]):
        frame[3] = agg[1]
    frame[4] += agg[2]
    frame[5] += agg[3]
    frame[6] += agg[4]
    frame[7] += agg[5]


def _gantt_bars(nodes, window_start, window_days, critical_ids):
    """The bars list — one dict per WBS node in TREE order.

    ``nodes`` is the project's task list in ``sequence``, ``id`` order (fetched once by the
    view — the same list feeds the window's date union). Subtree aggregates are computed
    ITERATIVELY (post-order over explicit frames; cycle edges contribute nothing), then the
    bars are emitted pre-order with their depth.
    """
    if not nodes:
        return []
    children_of = {}
    for node in nodes:
        children_of.setdefault(node.parent_id, []).append(node)

    # finished: pk -> (start, end, wp_count, effort_total, weighted_total, plain_total); a
    # frame is [node, child iterator, start, end, wp_count, effort, weighted, plain].
    finished = {}
    for seed in nodes:
        if seed.pk in finished:
            continue
        stack = [[seed, iter(children_of.get(seed.pk, ())), None, None, 0, 0.0, 0.0, 0.0]]
        in_progress = {seed.pk}
        while stack:
            frame = stack[-1]
            child = next(frame[1], None)
            if child is not None:
                if child.pk in finished:
                    _merge_subtree(frame, finished[child.pk])
                elif child.pk not in in_progress:
                    in_progress.add(child.pk)
                    stack.append(
                        [child, iter(children_of.get(child.pk, ())),
                         None, None, 0, 0.0, 0.0, 0.0])
                continue
            stack.pop()
            in_progress.discard(frame[0].pk)
            node = frame[0]
            if node.node_type == "work_package":
                pct = float(node.percent_complete or 0)
                effort = float(node.effort_hours or 0)
                agg = (node.planned_start, node.planned_end, 1, effort, pct * effort, pct)
            else:
                agg = (frame[2], frame[3], frame[4], frame[5], frame[6], frame[7])
            finished[node.pk] = agg
            if stack:
                _merge_subtree(stack[-1], agg)

    bars = []
    emitted = set()
    stack = [(node, 0) for node in reversed(children_of.get(None, []))]
    while stack:
        node, depth = stack.pop()
        if node.pk in emitted or depth >= _GANTT_MAX_DEPTH:
            continue
        emitted.add(node.pk)
        if node.node_type == "work_package":
            start, end = node.planned_start, node.planned_end
            progress = float(node.percent_complete or 0)
        else:
            start, end, wp_count, effort_total, weighted, plain = finished[node.pk]
            if wp_count:
                progress = (round(weighted / effort_total, 1) if effort_total > 0
                            else round(plain / wp_count, 1))
            else:
                progress = None
        left_pct = width_pct = None
        if start and end:
            left_pct = round(100.0 * (start - window_start).days / window_days, 2)
            # max(..., 1): an inverted date pair cannot go below a one-day bar.
            width_pct = round(100.0 * max((end - start).days + 1, 1) / window_days, 2)
        bars.append({
            "task": node,
            "depth": depth,
            "left_pct": left_pct,
            "width_pct": width_pct,
            "progress_pct": progress,
            "is_critical": node.pk in critical_ids,
            "is_deliverable": node.node_type == "deliverable",
        })
        for child in reversed(children_of.get(node.pk, [])):
            stack.append((child, depth + 1))
    return bars


def _dependency_rows(project):
    """The links-table rows and the finish-to-start date conflicts, from ONE queryset.

    ``dep_rows`` render beside the chart (arrows are JS → deferred); ``conflicts`` are the FS
    links whose successor starts before its predecessor ends — both dates must be set, so a
    half-dated pair is simply not comparable and never flagged. Ordered successor-first so a
    task's incoming links read together.
    """
    deps = (TaskDependency.objects
            .filter(predecessor__project_id=project.pk, successor__project_id=project.pk)
            .select_related("predecessor", "successor")
            .order_by("successor_id", "predecessor_id", "id"))
    dep_rows, conflicts = [], []
    for dep in deps:
        dep_rows.append({
            "dependency": dep,
            "predecessor": dep.predecessor,
            "successor": dep.successor,
            "link_type_label": dep.get_link_type_display(),
            "lag_days": dep.lag_days,
        })
        if (dep.link_type == "finish_to_start"
                and dep.successor.planned_start and dep.predecessor.planned_end
                and dep.successor.planned_start < dep.predecessor.planned_end):
            conflicts.append(dep)
    return dep_rows, conflicts


@login_required
def gantt_timeline(request):
    """Bullet 4's Gantt — the CSS bar chart over the resolved window, the dependency links
    table and the FS date conflicts, all computed on read.

    ``?project=`` scopes the page (``None`` → the picker empty state); it is the only scoping
    parameter this page parses (the contract pins ``?start=``/``?end=`` for the window and
    nothing else). Junk or out-of-tenant ids degrade to the empty state, never a 500.
    """
    tenant = request.tenant
    project_qs = project_choices(tenant)
    today = timezone.localdate()

    project = None
    project_id = as_db_int(request.GET.get("project"))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()

    bars, dep_rows, conflicts, critical_ids, window = [], [], [], set(), None
    if project is not None:
        nodes = list(project.tasks.order_by("sequence", "id"))
        starts = [node.planned_start for node in nodes if node.planned_start]
        ends = [node.planned_end for node in nodes if node.planned_end]
        # Each side of the default resolves independently (the union's earliest start / latest
        # end, padded); a side with no dates falls to the undated default below.
        default_start = (min(starts) - timedelta(days=_WINDOW_PAD_DAYS)) if starts else today
        default_end = ((max(ends) + timedelta(days=_WINDOW_PAD_DAYS)) if ends
                       else today + timedelta(days=_DEFAULT_SPAN_DAYS))

        form = _GanttWindowForm(request.GET)
        # full_clean runs once here; each side is then read independently (the 7.5 params
        # idiom) — a junk ?start= falls to its default WITHOUT discarding a valid ?end=,
        # because add_error drops only the failing field from cleaned_data.
        form.is_valid()
        start = form.cleaned_data.get("start")
        end = form.cleaned_data.get("end")
        window_start, window_end, window_days = _resolve_window(
            start, end, default_start, default_end)
        window = {"start": window_start, "end": window_end, "days": window_days}

        critical_ids = critical_path_ids(project)
        bars = _gantt_bars(nodes, window_start, window_days, critical_ids)
        dep_rows, conflicts = _dependency_rows(project)

    return render(request, "projects/taskwork/gantt_timeline.html", {
        "projects": project_qs,
        "project": project,
        "window": window,
        "bars": bars,
        "critical_ids": critical_ids,
        "dep_rows": dep_rows,
        "conflicts": conflicts,
        "today": today,
    })
