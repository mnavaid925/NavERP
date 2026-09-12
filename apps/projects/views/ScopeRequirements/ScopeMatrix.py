"""Projects 7.7 — the computed scope traceability matrix + creep-control board.

Bullet 2 ("traceability matrices") and the control half of bullet 5 ("scope creep alerts") in one
**computed** page — nothing here is stored, and deliberately so. A matrix is a *view over* the
requirement register's ``wbs_node`` links and the verification log, and a creep figure is a *view
over* the approved change requests; a stored copy of either goes stale the instant somebody links a
requirement or approves a change (the 7.5 "no stored simulation, no snapshot table" ruling, and the
7.3 ``capacity_demand`` precedent for a computed page rather than a model).

Three panels:

* **The traceability matrix** — requirements (rows) × the project's work packages (columns). A cell
  is filled when the requirement names that work package as its deliverer. The coverage figures read
  the same links, so the matrix and the counters cannot disagree.
* **The gaps** — requirements with no work package (untraced) and approved/implemented requirements
  that were never verified. These are the two things a traceability review actually looks for.
* **Scope creep** — approved and implemented change requests aggregated per month, with their cost
  and schedule totals. The creep signal is the *accumulation*, so the rows are ordered by period and
  the bars are drawn as a share of the largest month.

The page is GET-only and every figure is derived on read. ``?project=`` is ``as_db_int``-guarded
(L11) so a hand-typed value skips the scope rather than 500ing.
"""
from django.db.models import Count, Q

from apps.core.crud import as_db_int
from apps.projects.models import (
    Project,
    ProjectTask,
    Requirement,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
)
from apps.projects.models._base import ZERO, q2
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render

#: The matrix's column cap. Beyond this the grid stops being readable, and the coverage counters
#: below it carry the summary instead.
MAX_MATRIX_COLUMNS = 12
#: The matrix's row cap for the same reason.
MAX_MATRIX_ROWS = 40
#: The gap lists are review queues, not registers — the register is one click away.
GAP_LIMIT = 25
#: The creep loop's row cap. The board aggregates approved/implemented changes per month, and the
#: figure is a control signal, not an audit — the register (``scr_list``) is one click away. Without
#: a cap a project with thousands of approved changes would materialize every row in Python just to
#: sum a handful of monthly totals.
CREEP_LIMIT = 500

_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(value):
    return f"{_MONTH_LABELS[value.month - 1]} {value.year}"


@login_required
def scope_matrix(request):
    tenant = request.tenant
    projects = Project.objects.filter(tenant=tenant).order_by("name")
    project_id = as_db_int(request.GET.get("project", ""))
    project = Project.objects.filter(tenant=tenant, pk=project_id).first() if project_id else None

    requirements_qs = Requirement.objects.filter(tenant=tenant)
    changes_qs = ScopeChangeRequest.objects.filter(tenant=tenant)
    items_qs = ScopeItem.objects.filter(tenant=tenant)
    verifications_qs = ScopeVerification.objects.filter(tenant=tenant)
    if project is not None:
        requirements_qs = requirements_qs.filter(project=project)
        changes_qs = changes_qs.filter(project=project)
        items_qs = items_qs.filter(project=project)
        verifications_qs = verifications_qs.filter(project=project)

    # -- the matrix's columns: the project's work packages --------------------------------
    if project is not None:
        wp_qs = ProjectTask.objects.filter(
            tenant=tenant, project=project, node_type="work_package").order_by("sequence", "id")
        wp_total = wp_qs.count()
        work_packages = list(wp_qs[:MAX_MATRIX_COLUMNS])
    else:
        work_packages, wp_total = [], 0

    # -- coverage counters (one aggregate, not one query per figure) -----------------------
    coverage = requirements_qs.aggregate(
        total=Count("pk"),
        traced=Count("pk", filter=Q(wbs_node__isnull=False)),
        verified=Count("pk", filter=Q(status="verified")),
    )
    coverage["untraced"] = coverage["total"] - coverage["traced"]
    coverage["coverage_pct"] = (
        round(coverage["traced"] / coverage["total"] * 100, 1) if coverage["total"] else 0.0)

    # -- per-requirement verification counts, two grouped queries (no per-row N+1) ---------
    verification_counts = {
        row["requirement_id"]: row["total"]
        for row in verifications_qs.filter(requirement__isnull=False)
        .values("requirement_id").annotate(total=Count("id"))
    }
    accepted_counts = {
        row["requirement_id"]: row["total"]
        for row in verifications_qs
        .filter(requirement__isnull=False, acceptance_status__in=("accepted", "waived"))
        .values("requirement_id").annotate(total=Count("id"))
    }

    matrix_rows = []
    for requirement in (requirements_qs
                        .select_related("wbs_node", "owner")
                        .order_by("-created_at", "-id")[:MAX_MATRIX_ROWS]):
        matrix_rows.append({
            "requirement": requirement,
            "cells": [requirement.wbs_node_id == wp.pk for wp in work_packages],
            "traced": requirement.wbs_node_id is not None,
            "verification_count": verification_counts.get(requirement.pk, 0),
            "verified_count": accepted_counts.get(requirement.pk, 0),
        })

    untraced = list(requirements_qs.filter(wbs_node__isnull=True)
                    .select_related("project").order_by("-created_at", "-id")[:GAP_LIMIT])
    unverified = list(requirements_qs.filter(status__in=("approved", "implemented"))
                      .select_related("project").order_by("-created_at", "-id")[:GAP_LIMIT])

    # -- scope creep: the approved/implemented changes, aggregated per month --------------
    # ``.values()`` fetches only the four columns the loop reads, and the (stable-ordered) slice
    # bounds the result set the way the two gap lists are bounded — the aggregate is a control
    # signal, not an audit, and the register is one click away.
    creep_rows_map = {}
    creep_count, creep_cost, creep_days, creep_high = 0, ZERO, 0, 0
    creep_changes = (changes_qs.filter(status__in=("approved", "implemented"))
                     .values("schedule_impact_days", "cost_impact", "quality_impact",
                             "decided_at", "created_at")
                     .order_by("-created_at", "-id")[:CREEP_LIMIT])
    for change in creep_changes:
        creep_count += 1
        cost = change["cost_impact"]
        days = change["schedule_impact_days"] or 0
        creep_cost += cost
        creep_days += days
        if (cost >= ScopeChangeRequest.HIGH_COST
                or days >= ScopeChangeRequest.HIGH_SCHEDULE_DAYS
                or change["quality_impact"] == "high"):
            creep_high += 1
        # ``decided_at`` is the approval instant the verb stamps; ``created_at`` is the fallback
        # for a row seeded straight into an approved state, so no change is silently dropped.
        stamp = change["decided_at"] or change["created_at"]
        key = (stamp.year, stamp.month)
        row = creep_rows_map.setdefault(
            key, {"period": f"{stamp.year}-{stamp.month:02d}", "label": _month_label(stamp),
                  "count": 0, "cost_total": ZERO, "schedule_days": 0})
        row["count"] += 1
        row["cost_total"] += cost
        row["schedule_days"] += days
    creep_rows = [creep_rows_map[key] for key in sorted(creep_rows_map)]
    creep_max = max((row["cost_total"] for row in creep_rows), default=ZERO)
    for row in creep_rows:
        row["cost_total"] = q2(row["cost_total"])
        row["bar_pct"] = (round(row["cost_total"] / creep_max * 100, 1)
                          if creep_max else 0.0)

    # -- the summary strip -----------------------------------------------------------------
    # One grouped aggregate per dimension replaces a ``.count()`` per choice: ten scalar tallies
    # become two queries. ``.get(value, 0)`` restores the zero rows the choice list expects.
    def _rows(choices, qs, field):
        totals = dict(qs.values_list(field).annotate(total=Count("id")))
        return [{"label": label, "count": totals.get(value, 0)} for value, label in choices]

    today = timezone.localdate()
    # The six registry figures in one pass over ``item_type`` / ``status`` / ``review_date``:
    # ``item_type`` yields items/boundaries/constraints/assumptions, and a single filtered
    # ``status`` aggregate yields still-live and review-overdue.
    item_type_totals = dict(items_qs.values_list("item_type").annotate(total=Count("id")))
    live = items_qs.filter(status__in=("open", "validated")).aggregate(
        total=Count("id"), overdue=Count("id", filter=Q(review_date__lt=today)))
    scope_summary = {
        "items": sum(item_type_totals.values()),
        "boundaries": sum(c for t, c in item_type_totals.items()
                          if t in ScopeItem.BOUNDARY_TYPES),
        "constraints": item_type_totals.get("constraint", 0),
        "assumptions": item_type_totals.get("assumption", 0),
        "open_items": live["total"],
        "overdue_items": live["overdue"],
    }

    return render(request, "projects/scope/scope_matrix.html", {
        "projects": projects,
        "project": project,
        "work_packages": work_packages,
        "wp_total": wp_total,
        "matrix_rows": matrix_rows,
        "coverage": coverage,
        "untraced": untraced,
        "unverified": unverified,
        "creep_rows": creep_rows,
        "creep_max": creep_max,
        "creep": {"count": creep_count, "cost_total": q2(creep_cost),
                  "schedule_days": creep_days, "high_impact_count": creep_high},
        "type_rows": _rows(Requirement.REQUIREMENT_TYPE_CHOICES, requirements_qs,
                           "requirement_type"),
        "priority_rows": _rows(Requirement.PRIORITY_CHOICES, requirements_qs, "priority"),
        "scope_summary": scope_summary,
    })
