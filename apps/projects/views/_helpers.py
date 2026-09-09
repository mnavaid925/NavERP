"""Private helpers used by MORE THAN ONE sub-module's views.

A helper used by a single entity stays in that entity's module. These three are each shared by
more than one of 7.1's registers, so they live here rather than being copy-pasted forward.

Both return ``.none()`` for a tenant-less user instead of raising: the superuser has
``tenant=None`` and sees no module data by design, so a filter dropdown for them is empty, not an
error.
"""
from apps.core.models import OrgUnit, Party
from apps.projects.models import Project


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


def critical_path_ids(project):
    """The project's critical chain, as a set of ``ProjectTask`` pks.

    Bullet 2 of 7.2 ("critical path calculation"), planning-grade: the critical path is the
    dependency chain of work packages whose summed durations is longest. A forward pass via
    memoised DFS over ``TaskDependency`` edges (predecessor → successor), then a deterministic
    walk back from the best endpoint marking the chain.

    Deliberate simplifications, both documented rather than hidden: undated tasks count as one
    day; ties break by ``(sequence, id)``; the result is ONE chain, not the full zero-float set
    a backward CPM pass would produce (early/late starts and total float are 7.16 reporting's).
    The ``visiting`` set makes a cycle in the data (not creatable through the forms) cost a
    skipped edge, not a RecursionError — and the recursion is bounded by the node count.
    """
    from apps.projects.models import TaskDependency

    tasks = list(project.tasks.filter(node_type="work_package").order_by("sequence", "id"))
    if not tasks:
        return set()
    preds = {}  # successor pk -> [predecessor tasks]
    deps = (TaskDependency.objects
            .filter(predecessor__project_id=project.pk, successor__project_id=project.pk)
            .select_related("predecessor", "successor")
            .order_by("predecessor_id", "successor_id"))
    for dep in deps:
        preds.setdefault(dep.successor_id, []).append(dep.predecessor)

    def duration(task):
        return task.duration_days if task.duration_days else 1

    best = {}  # pk -> (total_days, task_count) of the longest chain ENDING at this task

    def chain_length(task, visiting):
        if task.pk in best:
            return best[task.pk]
        if task.pk in visiting:  # cycle in the data: break the edge, don't the stack
            return (0, 0)
        visiting.add(task.pk)
        parents = preds.get(task.pk, [])
        if parents:
            length, count = max(
                (chain_length(p, visiting) for p in parents),
                key=lambda pair: (pair[0], pair[1]))
            length += duration(task)
            count += 1
        else:
            length, count = duration(task), 1
        visiting.discard(task.pk)
        best[task.pk] = (length, count)
        return best[task.pk]

    for task in tasks:
        chain_length(task, set())

    # Walk back from the best endpoint, following the predecessor the forward pass actually chose.
    end = max(tasks, key=lambda t: (best[t.pk][0], best[t.pk][1], -t.sequence, -t.pk))
    chain, cursor = {end.pk}, end
    while True:
        parents = [p for p in preds.get(cursor.pk, []) if p.pk in best]
        if not parents:
            break
        target = best[cursor.pk][0] - duration(cursor)
        matches = [p for p in parents if best[p.pk][0] == target]
        if not matches:
            break
        cursor = matches[0]
        chain.add(cursor.pk)
    return chain
