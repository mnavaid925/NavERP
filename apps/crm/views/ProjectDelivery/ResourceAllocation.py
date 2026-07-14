"""CRM 1.8 Project & Delivery Management — ResourceAllocation views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmProject,
    ResourceAllocation,
    Timesheet,
)
from apps.crm.forms import (
    ResourceAllocationForm,
)


DEFAULT_WEEKLY_CAPACITY = Decimal("40")  # planned-hours capacity per person per week (future: per-employee)


# ------------------------------------------------------------ 1.8 Resource Allocation
@login_required
def resourceallocation_list(request):
    return crud_list(
        request,
        ResourceAllocation.objects.filter(tenant=request.tenant).select_related("project", "assignee"),
        "crm/projects/resourceallocation/list.html",
        search_fields=["number", "role", "assignee__username", "project__name"],
        filters=[("status", "status", False), ("project", "project_id", True),
                 ("assignee", "assignee_id", True)],
        extra_context={"status_choices": ResourceAllocation.STATUS_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def resourceallocation_create(request):
    return crud_create(request, form_class=ResourceAllocationForm,
                       template="crm/projects/resourceallocation/form.html",
                       success_url="crm:resourceallocation_list")


@login_required
def resourceallocation_detail(request, pk):
    obj = get_object_or_404(
        ResourceAllocation.objects.select_related("project", "assignee"), pk=pk, tenant=request.tenant)
    return render(request, "crm/projects/resourceallocation/detail.html", {"obj": obj})


@login_required
def resourceallocation_edit(request, pk):
    return crud_edit(request, model=ResourceAllocation, pk=pk, form_class=ResourceAllocationForm,
                     template="crm/projects/resourceallocation/form.html",
                     success_url="crm:resourceallocation_list")


@login_required
@require_POST
def resourceallocation_delete(request, pk):
    return crud_delete(request, model=ResourceAllocation, pk=pk, success_url="crm:resourceallocation_list")


@login_required
def resource_workload(request):
    """1.8 Resource Allocation — the workload/capacity board: per person, planned (allocations) vs.
    logged (timesheets) vs. capacity over a date window, flagging overbooked / free capacity. Two
    grouped aggregates (allocations + timesheets) — no per-person N+1."""
    today = timezone.localdate()
    default_start = today - timedelta(days=today.weekday())  # this week's Monday
    start = parse_date(request.GET.get("start", "") or "") or default_start
    end = parse_date(request.GET.get("end", "") or "") or (start + timedelta(days=27))  # 4 weeks
    if end < start:
        end = start + timedelta(days=27)
    weeks = Decimal((end - start).days + 1) / Decimal(7)
    capacity = (DEFAULT_WEEKLY_CAPACITY * weeks).quantize(Decimal("0.01"))

    # Planned: allocations overlapping the window (prorated in Python via overlap_hours).
    allocs = list(ResourceAllocation.objects.filter(tenant=request.tenant)
                  .exclude(status="cancelled")
                  .filter(Q(end_date__gte=start) | Q(end_date__isnull=True), start_date__lte=end)
                  .select_related("assignee"))
    planned_by_user, name_by_user = {}, {}
    for a in allocs:
        if a.assignee_id is None:
            continue
        planned_by_user[a.assignee_id] = planned_by_user.get(a.assignee_id, Decimal("0")) + a.overlap_hours(start, end)
        name_by_user[a.assignee_id] = a.assignee

    # Logged: timesheet hours grouped by employee in the window (one query).
    logged_by_user = {r["employee"]: (r["h"] or Decimal("0")) for r in
                      Timesheet.objects.filter(tenant=request.tenant, date__gte=start, date__lte=end)
                      .exclude(status="rejected")  # rejected hours aren't real logged work (code-review)
                      .values("employee").annotate(h=Sum("hours"))}

    user_ids = {uid for uid in (set(planned_by_user) | set(logged_by_user)) if uid is not None}
    missing = [uid for uid in user_ids if uid not in name_by_user]
    if missing:  # resolve names for people who only have timesheets (no allocation)
        for u in User.objects.filter(tenant=request.tenant, pk__in=missing):
            name_by_user[u.pk] = u

    rows = []
    for uid in user_ids:
        planned = planned_by_user.get(uid, Decimal("0"))
        logged = logged_by_user.get(uid, Decimal("0"))
        util = int(planned / capacity * 100) if capacity else 0
        rows.append({"user": name_by_user.get(uid), "planned": planned, "logged": logged,
                     "capacity": capacity, "available": capacity - planned,
                     "util_pct": util, "overbooked": planned > capacity})
    rows.sort(key=lambda r: r["planned"], reverse=True)
    return render(request, "crm/projects/workload.html",
                  {"rows": rows, "start": start, "end": end, "capacity": capacity})
