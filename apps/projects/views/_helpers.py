"""Private helpers used by MORE THAN ONE sub-module's views.

A helper used by a single entity stays in that entity's module. The first three here are the
filter-dropdown builders shared by more than one of 7.1's/7.2's registers; the fourth,
``critical_path_ids``, is 7.2's critical-chain pass over dependency edges. Same rule for all
four: if only one consumer ever needs a helper, it moves to that consumer's module.

The dropdown builders return ``.none()`` for a tenant-less user instead of raising: the
superuser has ``tenant=None`` and sees no module data by design, so a filter dropdown for them
is empty, not an error. (``critical_path_ids`` is project-scoped, and a tenant-less user never
reaches it — their project dropdown is empty — and it returns an empty set for a plan with no
work packages.)
"""
from apps.core.models import OrgUnit, Party
from apps.projects.models import Project, ProjectRequest, ResourceProfile


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

    Meta.ordering (the people-list order) serves it; ``.none()`` for a tenant-less user.
    """
    if tenant is None:
        return ResourceProfile.objects.none()
    return ResourceProfile.objects.filter(tenant=tenant)


def project_requests(tenant):
    """This workspace's project requests, ordered for a dropdown (7.3's demand lens).

    Every status — a booking can hang off a request that is still being screened, and a
    dropdown that silently omits the one you need is worse than one that lists everyone
    (the ``clients()`` ruling).
    """
    if tenant is None:
        return ProjectRequest.objects.none()
    return ProjectRequest.objects.filter(tenant=tenant).order_by("title", "id")


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
