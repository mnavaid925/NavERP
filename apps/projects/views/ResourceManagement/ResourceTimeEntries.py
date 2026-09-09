"""Projects 7.3 — ResourceTimeEntry views (bullet 5: time tracking, approvals, actuals-to-plan).

The register is a flat paginated list; the weekly lens is template-side (``regroup`` over
``week_key``, contiguous under Meta.ordering). The **actuals-to-plan** section is computed in
the view over one ISO person-week window: approved hours per (resource, project) against the
live allocations' ``planned_hours`` for the same pair, ordered by variance. Approval verbs are
tenant-admin gated like every governance verb in this app; approved/rejected rows refuse edit
and delete (7.1 evidence ruling) and the stamps are written exactly once by the verbs.
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import ResourceTimeEntryForm
from apps.projects.models import ResourceAllocation, ResourceProfile, ResourceTimeEntry
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST, timezone)
from apps.projects.views._helpers import project_requests, projects, resource_profiles

_ZERO = Decimal("0")


def _actuals_rows(tenant, win_start, win_end):
    """Approved-vs-planned per (resource, project) inside [win_start, win_end].

    Rows are keyed by the pairs that actually logged approved time; ``planned_hours`` sums the
    LIVE (soft/firm) allocations of the same resource+project pair — a request-linked named
    booking lands under the ``project=None`` row ("Non-project time"), which is honest: that
    demand has no project to compare against yet.
    """
    actuals = {}
    approved = (ResourceTimeEntry.objects
                .filter(tenant=tenant, status="approved",
                        entry_date__gte=win_start, entry_date__lte=win_end)
                .select_related("resource", "project"))
    for entry in approved:
        key = (entry.resource_id, entry.project_id)
        row = actuals.get(key)
        if row is None:
            row = actuals[key] = {"resource": entry.resource, "project": entry.project,
                                  "actual_hours": _ZERO}
        row["actual_hours"] += entry.hours

    planned_by_pair = {}
    live_allocs = (ResourceAllocation.objects
                   .filter(tenant=tenant, resource_id__isnull=False,
                           booking_status__in=("soft", "firm"),
                           start_date__lte=win_end)
                   .filter(Q(end_date__isnull=True) | Q(end_date__gte=win_start)))
    for alloc in live_allocs:
        key = (alloc.resource_id, alloc.project_id)
        if key in actuals:
            # Only pairs that actually logged approved time render a row — skip the
            # planned_hours() call for every other live allocation in the window.
            planned_by_pair[key] = (planned_by_pair.get(key, _ZERO)
                                    + alloc.planned_hours(win_start, win_end))

    rows = []
    for (resource_id, project_id), row in actuals.items():
        planned = planned_by_pair.get((resource_id, project_id), _ZERO)
        rows.append({
            "resource": row["resource"],
            "project": row["project"],
            "actual_hours": row["actual_hours"].quantize(Decimal("0.01")),
            "planned_hours": planned,
            "variance": (row["actual_hours"] - planned).quantize(Decimal("0.01")),
        })
    rows.sort(key=lambda r: r["variance"], reverse=True)
    return rows


@login_required
def rte_list(request):
    qs = (ResourceTimeEntry.objects.filter(tenant=request.tenant)
          .select_related("resource__employee__party", "resource__party",
                          "project", "project_task"))
    # The actuals window: ?year=+?week= when both parse, else the current ISO week. The pair is
    # ISO-consistent (the register filter uses the same lookups); a nonsense combo (week 99)
    # falls back to the current week rather than 500ing on fromisocalendar.
    today = timezone.localdate()
    year = as_db_int(request.GET.get("year"))
    week = as_db_int(request.GET.get("week"))
    # L11: a year that cannot exist (0, or 9999+ — the ISO bounds compute year+1, so 9999
    # itself already overflows) can never match a row — but Django's year-lookup bounds
    # RAISE on it inside .count(). Empty the register up front instead (qs.none()
    # short-circuits the bounds compile). ?week=0/99 need no guard: SQL WEEK() simply
    # matches nothing, which is the contract's documented behavior.
    if year is not None and not 1 <= year <= 9998:
        qs = qs.none()
        year = None
    if year is None or week is None:
        iso = today.isocalendar()
        year, week = iso[0], iso[1]
    try:
        win_start = date.fromisocalendar(year, week, 1)
        win_end = date.fromisocalendar(year, week, 7)
    except ValueError:
        iso = today.isocalendar()
        year, week = iso[0], iso[1]
        win_start = date.fromisocalendar(year, week, 1)
        win_end = date.fromisocalendar(year, week, 7)
    return crud_list(
        request, qs, "projects/resource/resourcetimeentry/list.html",
        search_fields=["number", "task_description", "resource__employee__party__name",
                       "resource__party__name", "project__name"],
        filters=[("status", "status", False),
                 ("resource", "resource_id", True),
                 ("project", "project_id", True),
                 ("year", "entry_date__iso_year", True),
                 ("week", "entry_date__week", True)],
        extra_context={
            "status_choices": ResourceTimeEntry.STATUS_CHOICES,
            "resources": resource_profiles(request.tenant),
            "projects": projects(request.tenant),
            "actuals_rows": _actuals_rows(request.tenant, win_start, win_end),
            "actuals_year": year,
            "actuals_week": week,
        },
    )


@login_required
def rte_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ResourceTimeEntryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Time entry {obj.number} created.")
            return redirect("projects:rte_detail", pk=obj.pk)
    else:
        form = ResourceTimeEntryForm(tenant=request.tenant,
                                     initial={"resource": request.GET.get("resource", "")})
    return render(request, "projects/resource/resourcetimeentry/form.html",
                  {"form": form, "is_edit": False})


@login_required
def rte_detail(request, pk):
    obj = get_object_or_404(
        ResourceTimeEntry.objects.select_related(
            "resource", "project", "project_task", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/resource/resourcetimeentry/detail.html", {"obj": obj})


@login_required
def rte_edit(request, pk):
    obj = get_object_or_404(ResourceTimeEntry, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "An approved or rejected entry is locked — it cannot be edited.")
        return redirect("projects:rte_detail", pk=obj.pk)
    return crud_edit(
        request, model=ResourceTimeEntry, pk=pk, form_class=ResourceTimeEntryForm,
        template="projects/resource/resourcetimeentry/form.html",
        success_url="projects:rte_list")


@login_required
@require_POST
def rte_delete(request, pk):
    obj = get_object_or_404(ResourceTimeEntry, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "An approved or rejected entry is locked — it cannot be deleted.")
        return redirect("projects:rte_detail", pk=obj.pk)
    return crud_delete(request, model=ResourceTimeEntry, pk=pk,
                       success_url="projects:rte_list")


@login_required
@require_POST
def rte_submit(request, pk):
    obj = get_object_or_404(ResourceTimeEntry, pk=pk, tenant=request.tenant)
    if obj.status == "submitted":
        messages.info(request, "That entry is already awaiting approval.")
        return redirect("projects:rte_detail", pk=obj.pk)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "An approved or rejected entry cannot be submitted.")
        return redirect("projects:rte_detail", pk=obj.pk)
    obj.status = "submitted"
    obj.submitted_at = timezone.now()
    obj.save(update_fields=["status", "submitted_at", "updated_at"])
    write_audit_log(request.user, obj, "submit", changes={"verb": "submit"})
    messages.success(request, f"Entry {obj.number} submitted for approval.")
    return redirect("projects:rte_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def rte_approve(request, pk):
    obj = get_object_or_404(ResourceTimeEntry, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(
            request,
            f"Only a submitted entry can be approved — this one is "
            f"{obj.get_status_display().lower()}.")
        return redirect("projects:rte_detail", pk=obj.pk)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "approve", changes={"verb": "approve"})
    messages.success(request, f"Entry {obj.number} approved.")
    return redirect("projects:rte_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def rte_reject(request, pk):
    obj = get_object_or_404(ResourceTimeEntry, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(
            request,
            f"Only a submitted entry can be rejected — this one is "
            f"{obj.get_status_display().lower()}.")
        return redirect("projects:rte_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.decision_note = request.POST.get("reason", "").strip()
    obj.save(update_fields=["status", "approved_by", "approved_at", "decision_note", "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "reason": obj.decision_note})
    messages.success(request, f"Entry {obj.number} rejected.")
    return redirect("projects:rte_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def rte_approve_week(request, resource, year, week):
    """Bulk-approve every submitted entry of one person-week (the approval-queue verb).

    One audit row for the batch — per-entry rows for a 40-entry week would be noise; the
    ``changes`` payload carries the week and the count.
    """
    person = get_object_or_404(ResourceProfile, pk=resource, tenant=request.tenant)
    if not 1 <= week <= 53:
        messages.error(request, "Week must be between 1 and 53.")
        return redirect("projects:rte_list")
    try:
        date.fromisocalendar(year, week, 1)
    except ValueError:
        messages.error(request, f"{year} week {week} is not a real ISO week.")
        return redirect("projects:rte_list")
    entries = list(ResourceTimeEntry.objects
                   .filter(tenant=request.tenant, resource=person, status="submitted",
                           entry_date__iso_year=year, entry_date__week=week)
                   .order_by("entry_date", "id"))
    if not entries:
        messages.info(request, f"No submitted entries for {person.name} in week {week}.")
        return redirect("projects:rte_list")
    now = timezone.now()
    with transaction.atomic():
        for entry in entries:
            entry.status = "approved"
            entry.approved_by = request.user
            entry.approved_at = now
            entry.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, person, "approve",
                        changes={"verb": "approve_week", "week": f"{year}-W{week:02d}",
                                 "count": len(entries)})
    messages.success(request,
                     f"Approved {len(entries)} entries for {person.name}, week {week}.")
    return redirect("projects:rte_list")
