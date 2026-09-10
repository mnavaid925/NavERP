"""Projects 7.3 — the Capacity & Demand board (bullets 2 and 4, computed on read; no model).

Two tables over one ISO-week horizon (default 8, clamp 4..13):

* **Capacity** — per ACTIVE resource-week, the sum of soft/firm bookings'
  ``planned_hours`` against ``weekly_capacity_hours``; ``over`` flags the cell and
  ``over_count`` drives the alert line. Leveling here is the market norm the research found
  (Float/Resource Guru/Planview all flag-and-manually-rebalance): the alert plus the register's
  assign/substitute verbs ARE the smoothing workflow — there is no auto-smoothing engine.
* **Demand** (``id="demand"``) — requested/soft bookings overlapping the horizon, project-linked
  first. ``is_gap`` marks the unfilled placeholders: the hiring/outsourcing trigger.

Caveat stated on the page: capacity is uniform weekly hours — leave and absence (HRM 3.10) are
not deducted yet.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.models import ResourceAllocation, ResourceProfile
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render, timezone

DEFAULT_WEEKS = 8
MIN_WEEKS, MAX_WEEKS = 4, 13


@login_required
def capacity_demand(request):
    tenant = request.tenant
    today = timezone.localdate()
    monday = date.fromisocalendar(today.isocalendar()[0], today.isocalendar()[1], 1)

    weeks = as_db_int(request.GET.get("weeks")) or DEFAULT_WEEKS
    weeks = max(MIN_WEEKS, min(MAX_WEEKS, weeks))

    week_windows = []
    for offset in range(weeks):
        start = monday + timedelta(weeks=offset)
        week_windows.append({
            "year": start.isocalendar()[0],
            "week": start.isocalendar()[1],
            "start": start,
            "end": start + timedelta(days=6),
            "label": f"W{start.isocalendar()[1]} · {start:%b} {start.day}",
        })
    horizon_start, horizon_end = week_windows[0]["start"], week_windows[-1]["end"]

    # -- capacity: soft/firm bookings per active resource-week -------------------------------
    profiles = list(ResourceProfile.objects.filter(tenant=tenant, status="active")
                    .select_related("employee__party", "party", "org_unit"))
    capacity_allocs = (ResourceAllocation.objects
                       .filter(tenant=tenant, resource_id__isnull=False,
                               booking_status__in=("soft", "firm"),
                               start_date__lte=horizon_end)
                       .filter(Q(end_date__isnull=True) | Q(end_date__gte=horizon_start))
                       .select_related("resource"))
    allocs_by_resource = defaultdict(list)
    for alloc in capacity_allocs:
        allocs_by_resource[alloc.resource_id].append(alloc)

    over_count = 0
    for profile in profiles:
        cells = []
        for window in week_windows:
            planned = sum(alloc.planned_hours(window["start"], window["end"])
                          for alloc in allocs_by_resource.get(profile.pk, []))
            over = planned > profile.weekly_capacity_hours
            if over:
                over_count += 1
            cells.append({"planned": planned, "over": over})
        profile.cells = cells

    # -- demand: requested/soft bookings the pipeline and projects still carry ----------------
    demand_qs = (ResourceAllocation.objects.filter(tenant=tenant)
                 .filter(booking_status__in=("requested", "soft"),
                         start_date__lte=horizon_end)
                 .filter(Q(end_date__isnull=True) | Q(end_date__gte=horizon_start))
                 .select_related("project", "project_request", "resource"))
    demand_rows = (list(demand_qs.filter(project__isnull=False).order_by("start_date", "-id"))
                   + list(demand_qs.filter(project__isnull=True).order_by("start_date", "-id")))
    for alloc in demand_rows:
        if alloc.project_id:
            alloc.demand_label = alloc.project.name
            alloc.demand_url_name = "projects:prj_detail"
            alloc.demand_url_pk = alloc.project_id
        elif alloc.project_request_id:
            alloc.demand_label = alloc.project_request.title
            alloc.demand_url_name = "projects:prq_detail"
            alloc.demand_url_pk = alloc.project_request_id
        else:
            alloc.demand_label = "—"
            alloc.demand_url_name = None
            alloc.demand_url_pk = None
        alloc.demand_hours = sum(alloc.planned_hours(window["start"], window["end"])
                                 for window in week_windows)
        alloc.is_gap = alloc.resource_id is None

    return render(request, "projects/resource/capacity_demand.html", {
        "weeks": weeks,
        "week_windows": week_windows,
        "capacity_rows": profiles,
        "over_count": over_count,
        "demand_rows": demand_rows,
        "gap_count": len([alloc for alloc in demand_rows if alloc.is_gap]),
    })
