"""HRM 3.2 Organizational Structure — OrgChart views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
)


# ============================================================ Org Chart & Company Setup (3.2 — derived)
@login_required
def org_chart(request):
    """Reporting-line / department-grouped org chart, DERIVED from ``core.Employment.manager``
    (single-parent chain) and ``OrgUnit`` — no model. ``?view=reporting|department`` toggles mode."""
    tenant = request.tenant
    view_mode = "department" if request.GET.get("view") == "department" else "reporting"
    CAP = 500  # an org chart loads ALL employees (no pagination); guard against a runaway tenant.
    tree_nodes, dept_groups, total, capped = [], [], 0, False
    if tenant is not None:
        employees = list(
            EmployeeProfile.objects.filter(tenant=tenant)
            .exclude(employment__status="terminated")  # keep active/on-leave/unassigned, drop exited
            .select_related("party", "employment", "employment__org_unit", "employment__manager",
                            "designation", "designation__job_grade")
            .order_by("party__name")[:CAP + 1])
        capped = len(employees) > CAP
        if capped:
            employees = employees[:CAP]
        total = len(employees)
        # Map a manager Party -> the EmployeeProfile rows that report to it.
        by_party = {e.party_id: e for e in employees}
        children = {}
        roots = []
        for e in employees:
            mgr_party = e.employment.manager_id if e.employment_id else None
            if mgr_party and mgr_party in by_party and by_party[mgr_party].pk != e.pk:
                children.setdefault(mgr_party, []).append(e)
            else:
                roots.append(e)
        # Iterative DFS into a flat (employee, depth) list — cycle-guarded AND recursion-free in
        # Python too, so a very deep manager chain can't raise RecursionError (review C1).
        seen = set()
        stack = [(root, 0) for root in reversed(roots)]
        while stack:
            emp, depth = stack.pop()
            if emp.pk in seen:
                continue
            seen.add(emp.pk)
            tree_nodes.append({"emp": emp, "depth": depth})
            for child in reversed(children.get(emp.party_id, [])):
                stack.append((child, depth + 1))
        # Any employee not reached (cycle) is appended at depth 0 so none are dropped.
        for e in employees:
            if e.pk not in seen:
                tree_nodes.append({"emp": e, "depth": 0})

        # Department-grouped mode.
        groups = {}
        for e in employees:
            unit = e.employment.org_unit if e.employment_id else None
            key = unit.name if unit else "Unassigned"
            groups.setdefault(key, []).append(e)
        dept_groups = [{"name": name, "employees": groups[name]} for name in sorted(groups)]
    return render(request, "hrm/organization/org_chart.html", {
        "tree_nodes": tree_nodes,
        "dept_groups": dept_groups,
        "view_mode": view_mode,
        "total": total,
        "capped": capped,
        "cap": CAP,
    })
