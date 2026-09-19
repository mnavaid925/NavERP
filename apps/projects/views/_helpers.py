"""Private helpers used by MORE THAN ONE sub-module's views.

A helper used by a single entity stays in that entity's module. ``org_units``, ``clients``
and ``projects`` are the filter-dropdown builders shared by more than one of 7.1's/7.2's
registers; ``resource_profiles`` and ``project_requests`` are 7.3's demand-lens pair (the
request builder has one consumer today but is kept beside the pool builder it mirrors);
``critical_path_ids`` is 7.2's critical-chain pass over dependency edges; ``owners`` is 7.5's
owner/approver/escalation-target dropdown, shared by all four of that sub-module's registers; and
``csv_safe`` / ``redirect_back_or`` / ``csv_response`` and ``chart_config`` / ``chart_rows`` are 7.16's,
each read by more than one of that sub-module's five view modules; ``DASHBOARD_ORDER`` joins them for
the same reason, because three grouped reads of one model must order identically. Same rule for all
fourteen: if only one consumer ever needs a helper, it moves to that consumer's module.

The dropdown builders return ``.none()`` for a tenant-less user instead of raising: the
superuser has ``tenant=None`` and sees no module data by design, so a filter dropdown for them
is empty, not an error. (``critical_path_ids`` is project-scoped, and a tenant-less user never
reaches it — their project dropdown is empty — and it returns an empty set for a plan with no
work packages.)
"""
import csv

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.models import OrgUnit, Party
from apps.projects import analytics
from apps.projects.models import (
    Project, ProjectDashboard, ProjectRequest, Requirement, ResourceProfile,
)
from apps.projects.models.ReportingBusinessIntelligence._choices import CANVAS_CHARTS


def org_units(tenant):
    """This workspace's OrgUnits, ordered for a filter dropdown."""
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


def clients(tenant):
    """This workspace's Parties — a client is a Party with (or without) a customer role.

    Deliberately not filtered to ``PartyRole.role == "customer"``: a project's client can be any
    organisation on the spine, and a dropdown that silently omits the one you need is worse than
    one that lists everyone.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant).order_by("name")


def projects(tenant):
    """This workspace's Projects, ordered for a filter dropdown.

    Shared by the stakeholder register and the kickoff register — it was copy-pasted
    byte-identically into both entity modules, which is where two copies drift.
    """
    if tenant is None:
        return Project.objects.none()
    return Project.objects.filter(tenant=tenant).order_by("name")


def resource_profiles(tenant):
    """This workspace's resource pool, ordered for a dropdown (7.3's registers and board).

    ``name`` walks ``employee → party`` (or ``party``), so every label rendered from these
    rows selects the walk up front. Meta.ordering (the people-list order) serves it;
    ``.none()`` for a tenant-less user.
    """
    if tenant is None:
        return ResourceProfile.objects.none()
    return ResourceProfile.objects.filter(tenant=tenant).select_related(
        "employee__party", "party")


def project_requests(tenant):
    """This workspace's project requests, ordered for a dropdown (7.3's demand lens).

    Every status — a booking can hang off a request that is still being screened, and a
    dropdown that silently omits the one you need is worse than one that lists everyone
    (the ``clients()`` ruling).
    """
    if tenant is None:
        return ProjectRequest.objects.none()
    return ProjectRequest.objects.filter(tenant=tenant).order_by("title", "id")


def owners(tenant):
    """This workspace's users, ordered for an owner / approver / escalation-target dropdown.

    Shared by all four of 7.5's registers (the risk owner, the response-action owner, the issue
    owner and the escalation target are all the same population) — it was about to be copy-pasted
    into four entity modules, which is where four copies drift. Ordered by email because a user's
    display name is composed in the template (``get_full_name|default:email``), not a column.
    ``.none()`` for a tenant-less user, the ``org_units`` ruling.
    """
    if tenant is None:
        return get_user_model().objects.none()
    return get_user_model().objects.filter(tenant=tenant).order_by("email")


def requirements(tenant):
    """This workspace's requirements, ordered for a filter dropdown (7.7's registers).

    Shared by the change-request and verification registers — the requirement a change rewrites and
    the requirement an inspection verifies are the same population, so it is one builder rather than
    two copies that drift. Ordered by ``number`` (a human-readable per-tenant id, so the dropdown
    reads in the order the register does). ``.none()`` for a tenant-less user, the ``org_units``
    ruling.
    """
    if tenant is None:
        return Requirement.objects.none()
    return Requirement.objects.filter(tenant=tenant).order_by("number")


def critical_path_ids(project):
    """The project's critical chain, as a set of ``ProjectTask`` pks.

    Bullet 2 of 7.2 ("critical path calculation"), planning-grade: the critical path is the
    dependency chain of work packages whose summed durations is longest. One ITERATIVE longest-
    path pass over ``TaskDependency`` edges (predecessor → successor) in Kahn topological order
    (in-degree over the dependency edges), then a deterministic walk back from the best endpoint
    marking the chain. Iterative on purpose: a member-triggerable ~1000-task chain must not be
    able to RecursionError the tree page the way a memoised DFS could.

    Deliberate simplifications and bounds, documented rather than hidden:

    * A task's contribution is ``max(duration_days or 1, 1)`` — undated tasks count one day, and
      an inverted/negative window cannot go below one either, so the walk-back's strictly
      decreasing invariant holds for any hand-entered dates.
    * Ties break by ``(sequence, id)``: each successor's candidate predecessors are sorted that
      way ONCE when ``preds`` is built, and both the forward pass (``max`` keeps the first
      maximal candidate) and the walk-back (first match in that sorted order) consume them in it.
    * A cycle in the data (not creatable through the forms) means its nodes' in-degrees never
      reach zero: they never resolve, get no ``best`` entry, and are skipped — as are all nodes
      downstream of the cycle. A defensive processed-count cap bounds the queue loop even if the
      graph were somehow corrupt. The acyclic remainder of the plan still computes.
    * The result is ONE chain, not the full zero-float set a backward CPM pass would produce
      (early/late starts and total float are 7.16 reporting's).
    """
    from apps.projects.models import TaskDependency

    tasks = list(project.tasks.filter(node_type="work_package").order_by("sequence", "id"))
    if not tasks:
        return set()
    preds = {}  # successor pk -> [predecessor tasks], sorted by (sequence, id)
    deps = (TaskDependency.objects
            .filter(predecessor__project_id=project.pk, successor__project_id=project.pk)
            .select_related("predecessor", "successor")
            .order_by("predecessor_id", "successor_id"))
    node_by_pk = {t.pk: t for t in tasks}  # dep endpoints may include non-work-package nodes
    for dep in deps:
        preds.setdefault(dep.successor_id, []).append(dep.predecessor)
        node_by_pk.setdefault(dep.predecessor_id, dep.predecessor)
        node_by_pk.setdefault(dep.successor_id, dep.successor)
    for plist in preds.values():
        plist.sort(key=lambda t: (t.sequence, t.pk))

    def duration(task):
        return max(task.duration_days or 1, 1)

    # Kahn's in-degree order over the dependency edges. Every dep endpoint belongs to the
    # project (the queryset filters on it), so every edge below connects two graph nodes.
    graph = set(node_by_pk)
    succs = {pk: [] for pk in graph}
    indegree = {pk: 0 for pk in graph}
    for succ_pk, plist in preds.items():
        for p in plist:
            indegree[succ_pk] += 1
            succs[p.pk].append(succ_pk)

    best = {}  # pk -> (total_days, task_count) of the longest chain ENDING at this task
    queue = [pk for pk in graph if indegree[pk] == 0]
    processed, cap = 0, len(graph)
    while queue and processed < cap:
        processed += 1
        pk = queue.pop()
        plist = preds.get(pk)
        if plist:
            days, count = max(
                (best[p.pk] for p in plist), key=lambda pair: (pair[0], pair[1]))
            best[pk] = (days + duration(node_by_pk[pk]), count + 1)
        else:
            best[pk] = (duration(node_by_pk[pk]), 1)
        for succ_pk in succs[pk]:
            indegree[succ_pk] -= 1
            if indegree[succ_pk] == 0:
                queue.append(succ_pk)
    if not any(t.pk in best for t in tasks):
        return set()  # every work package sits in (or downstream of) a cycle — nothing to mark

    # Walk back from the best endpoint, following the predecessor the forward pass actually
    # chose: the first (sequence, id)-ordered parent whose chain length matches the target.
    end = max((t for t in tasks if t.pk in best),
              key=lambda t: (best[t.pk][0], best[t.pk][1], -t.sequence, -t.pk))
    chain, cursor = {end.pk}, end
    while True:
        parents = preds.get(cursor.pk)
        if not parents:
            break
        target = best[cursor.pk][0] - duration(cursor)
        cursor = next((p for p in parents
                       if p.pk in best and best[p.pk][0] == target), None)
        if cursor is None:
            break
        chain.add(cursor.pk)
    return chain


# ---------------------------------------------------------------------------------------------
# 7.16 Reporting & Business Intelligence. Every helper below is read by MORE THAN ONE entity module of
# that sub-module (Backend rule 5): every CSV route in 7.16 writes user-authored text into a cell,
# five POST verbs across three modules must return the user to the page they were on, and the canned
# report page, a saved report and a frozen run all render the SAME result partials — so the two chart
# builders and the two layout constants they read are one source, not three copies that can disagree
# about which sections a kind has.
# ``csv_safe`` is a deliberate local copy of ``apps/procurement/views/_helpers.py:323`` — peer apps
# never import each other's internals, the same reason ``forms/_common.py`` is its own copy.
# ---------------------------------------------------------------------------------------------

#: A cell that opens with one of these is a formula the reader's spreadsheet EXECUTES, not a value.
#: TAB and CR are in the set because Excel strips leading whitespace BEFORE deciding what a cell is,
#: so a value that opens ``\t=`` arrives as ``=``.
_CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Neutralise spreadsheet formula injection: prefix a dangerous leading character.

    Report titles, project names and narrative text are typed by people, and a CSV that carries
    ``=cmd|'/c calc'!A1`` in a cell runs it on the reader's machine. The apostrophe makes the cell a
    string and changes nothing else about the value.
    """
    text = str(value)
    return f"'{text}" if text[:1] in _CSV_DANGEROUS else text


def redirect_back_or(request, fallback_name, **kwargs):
    """Honour a POSTed ``next`` only as a same-host target; otherwise redirect to ``fallback_name``.

    ``next`` arrives from a form the client controls, so trusting it unchecked is an open redirect —
    scheme-relative values (``//evil.example``) and absolute ones fall back here, not through.
    """
    candidate = request.POST.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(candidate)
    return redirect(fallback_name, **kwargs)


def csv_response(filename, columns, rows):
    """A CSV download for a register's exact rows — the ONE writer for both 7.16 export routes.

    `rep_csv` and `run_csv` differ only in where their rows come from, so the two rules that matter —
    every cell through `csv_safe`, the row set capped at `analytics.MAX_EXPORT_ROWS` — live here rather
    than in each route, where a third export could forget one.

    `filename` is header material and reaches the reader's browser unparsed, so callers pass a
    system-assigned `number`/pk and never `obj.name`: a newline or a quote in text somebody typed would
    otherwise become a second header line.
    """
    def cell(value):
        # A missing measure is None in the payload, and `csv_safe` would render it as the word "None".
        return csv_safe("" if value is None else value)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([cell(name) for name in columns])
    for row in rows[:analytics.MAX_EXPORT_ROWS]:
        writer.writerow([cell(value) for value in row])
    return response


#: The dashboard register's order, spelled EXPLICITLY at every grouped read.
#:
#: ``annotate(annotation_count=Count("widgets"))`` puts the SELECT in a GROUP BY, and Django
#: deliberately ignores a model's default ordering for a grouped query (verified
#: ``django/db/models/query.py`` — "A default ordering doesn't affect GROUP BY queries"), which is
#: also what makes ``Paginator`` emit its ``UnorderedObjectListWarning``
#: (``django/core/paginator.py:129-145``). Confirmed against this app's rows by
#: ``temp/rbi_pdb_probe.py`` step 7b: the annotated SQL ends at its GROUP BY with **no ORDER BY at
#: all**. Three of 7.16's reads carry that annotation, so all three must re-assert the order — an
#: unordered page window is L9's bug (a board on both pages or on neither) and an unordered
#: ``[:6]``/``[:4]`` slice is not "the first few", it is a few the database felt like.
#:
#: The keys are read off the model rather than re-typed, so the one definition of the order stays in
#: ``ProjectDashboard.Meta.ordering``; ``id`` is appended as the tiebreak because ``name`` carries no
#: per-tenant uniqueness (only ``(tenant, number)`` does) and a tie is the same non-determinism in a
#: smaller coat.
DASHBOARD_ORDER = (*ProjectDashboard._meta.ordering, "id")


#: The canvas id on a one-chart page: its canvas element is ``wchart`` plus this id, the same shape a
#: board uses with real widget pks. A canned page and a saved report each show one chart, so the id is
#: a constant rather than a per-row value — and it is ONE constant, because those two pages share
#: ``_result_chart.html``. A frozen run is the exception: it passes its own pk (see ``chart_config``).
SINGLE_CHART_ID = 0

#: The areas with a ``_standard_section_<area>.html`` partial on disk. A registry row naming any other
#: area is dropped here rather than raising while the page renders.
SECTION_AREAS = ("schedule", "cost", "risk", "quality", "resource", "scope", "agile", "trend")


def chart_config(chart_type, labels, data, *, chart_id=SINGLE_CHART_ID):
    """The one-entry canvas payload, or no entry at all.

    An HTML chart kind (kpi, gauge, table, heat) renders markup and gets no canvas — a blank canvas
    still answers 200, which is the failure nobody notices. No labels is nothing to plot.

    ``chart_id`` is the number the canvas element carries (``wchart<id>``), not a selector for this
    rule. A canned page and a saved report have no row of their own to name, so they keep
    ``SINGLE_CHART_ID``; a frozen run is the exception B2.3 pins — its canvas is
    ``wchart{{ obj.pk }}``, so that page passes the run pk and still gets the canvas-vs-markup
    decision from here. The parameter exists so that one difference is the ONLY thing a caller can
    vary; a page that rebuilt the entry to change an id would also own a copy of this rule.
    """
    if chart_type not in CANVAS_CHARTS or not labels:
        return []
    return [{"id": chart_id, "type": chart_type, "labels": labels, "data": data}]


def chart_rows(labels, data):
    """Label/value pairs for the HTML bar table a non-canvas kind renders instead."""
    return [{"label": label, "value": value} for label, value in zip(labels, data)]
