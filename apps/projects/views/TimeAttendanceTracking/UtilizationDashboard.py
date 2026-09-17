"""Projects 7.11 — Time Reporting & Utilization Dashboard (Bullets 3 & 5).

Chargeability ratios, overhead allocation, client billing splits, individual and team
utilization rates against target, and capacity vs demand vs actuals.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Sum, Q

from apps.core.crud import as_db_int
from apps.projects.models import (
    Project, ProjectOvertimeRecord, ResourceAllocation, ResourceProfile,
    ResourceTimeEntry, TimeActivityCode)
from apps.projects.models._base import q2
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render, timezone
from apps.projects.views._helpers import projects, resource_profiles

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


@login_required
def utilization_dashboard(request):
    tenant = request.tenant
    today = timezone.localdate()

    # Time window resolution: default to current month
    year = as_db_int(request.GET.get("year")) or today.year
    month = as_db_int(request.GET.get("month")) or today.month
    if not (1 <= month <= 12):
        month = today.month
    if not (2000 <= year <= 2100):
        year = today.year

    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timezone.timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timezone.timedelta(days=1)

    days_in_month = (end_date - start_date).days + 1
    weeks_in_month = Decimal(days_in_month) / Decimal("7.0")

    selected_project_id = as_db_int(request.GET.get("project"))
    selected_resource_id = as_db_int(request.GET.get("resource"))

    entries_qs = ResourceTimeEntry.objects.filter(
        tenant=tenant,
        entry_date__gte=start_date,
        entry_date__lte=end_date,
        status="approved",
    )
    overtime_qs = ProjectOvertimeRecord.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date,
        status="approved",
    )

    if selected_project_id:
        entries_qs = entries_qs.filter(project_id=selected_project_id)
        overtime_qs = overtime_qs.filter(project_id=selected_project_id)
    if selected_resource_id:
        entries_qs = entries_qs.filter(resource_id=selected_resource_id)
        overtime_qs = overtime_qs.filter(resource_id=selected_resource_id)

    total_hours = entries_qs.aggregate(s=Sum("hours"))["s"] or _ZERO
    billable_hours = entries_qs.filter(is_billable=True).aggregate(s=Sum("hours"))["s"] or _ZERO
    non_billable_hours = total_hours - billable_hours
    total_overtime_hours = overtime_qs.aggregate(s=Sum("overtime_hours"))["s"] or _ZERO

    chargeability_ratio = (
        (billable_hours / total_hours * _HUNDRED).quantize(Decimal("0.1"))
        if total_hours > _ZERO else _ZERO
    )

    pool = (ResourceProfile.objects.filter(tenant=tenant, status="active")
            .select_related("employee__party", "party", "org_unit"))
    if selected_resource_id:
        pool = pool.filter(id=selected_resource_id)

    individual_rows = []
    total_capacity_month = _ZERO

    for r in pool:
        month_capacity = (r.weekly_capacity_hours * weeks_in_month).quantize(Decimal("0.1"))
        total_capacity_month += month_capacity

        r_entries = entries_qs.filter(resource=r)
        r_total = r_entries.aggregate(s=Sum("hours"))["s"] or _ZERO
        r_billable = r_entries.filter(is_billable=True).aggregate(s=Sum("hours"))["s"] or _ZERO
        r_non_billable = r_total - r_billable
        r_ot = overtime_qs.filter(resource=r).aggregate(s=Sum("overtime_hours"))["s"] or _ZERO

        r_utilization = (
            (r_billable / month_capacity * _HUNDRED).quantize(Decimal("0.1"))
            if month_capacity > _ZERO else _ZERO
        )
        r_chargeability = (
            (r_billable / r_total * _HUNDRED).quantize(Decimal("0.1"))
            if r_total > _ZERO else _ZERO
        )

        target = Decimal(r.utilization_target_pct)
        if r_utilization >= target:
            badge_class = "badge-green"
            status_text = "Target Met"
        elif r_utilization >= (target - Decimal("10")):
            badge_class = "badge-amber"
            status_text = "Near Target"
        else:
            badge_class = "badge-red"
            status_text = "Below Target"

        individual_rows.append({
            "resource": r,
            "role": r.default_role,
            "org_unit": r.org_unit.name if r.org_unit else "—",
            "capacity": month_capacity,
            "target_pct": target,
            "total_hours": q2(r_total),
            "billable_hours": q2(r_billable),
            "non_billable_hours": q2(r_non_billable),
            "overtime_hours": q2(r_ot),
            "utilization_pct": r_utilization,
            "chargeability_pct": r_chargeability,
            "badge_class": badge_class,
            "status_text": status_text,
        })

    individual_rows.sort(key=lambda x: x["utilization_pct"], reverse=True)

    overall_utilization = (
        (billable_hours / total_capacity_month * _HUNDRED).quantize(Decimal("0.1"))
        if total_capacity_month > _ZERO else _ZERO
    )

    client_splits = []
    projects_qs = (Project.objects.filter(tenant=tenant)
                   .select_related("client")
                   .filter(id__in=entries_qs.filter(is_billable=True).values_list("project_id", flat=True)))
    
    for prj in projects_qs:
        client_name = prj.client.name if prj.client else "Internal / Non-Client"
        prj_billable = entries_qs.filter(project=prj, is_billable=True).aggregate(s=Sum("hours"))["s"] or _ZERO
        if prj_billable > _ZERO:
            pct = (prj_billable / billable_hours * _HUNDRED).quantize(Decimal("0.1")) if billable_hours > _ZERO else _ZERO
            client_splits.append({
                "client_name": client_name,
                "project_name": prj.name,
                "project_number": prj.number,
                "billable_hours": q2(prj_billable),
                "share_pct": pct,
            })
    client_splits.sort(key=lambda x: x["billable_hours"], reverse=True)

    overhead_splits = []
    activity_codes = {ac.code: ac for ac in TimeActivityCode.objects.filter(tenant=tenant)}
    
    non_billable_entries = entries_qs.filter(is_billable=False)
    cat_totals = {}
    for entry in non_billable_entries:
        code_obj = activity_codes.get(entry.activity_code)
        category_label = code_obj.get_category_display() if code_obj else "General Overhead"
        cat_totals[category_label] = cat_totals.get(category_label, _ZERO) + entry.hours

    for cat_name, cat_hours in cat_totals.items():
        cat_pct = (cat_hours / non_billable_hours * _HUNDRED).quantize(Decimal("0.1")) if non_billable_hours > _ZERO else _ZERO
        overhead_splits.append({
            "category": cat_name,
            "hours": q2(cat_hours),
            "share_pct": cat_pct,
        })
    overhead_splits.sort(key=lambda x: x["hours"], reverse=True)

    planned_allocations = (ResourceAllocation.objects
                           .filter(tenant=tenant,
                                   booking_status__in=("soft", "firm"),
                                   start_date__lte=end_date)
                           .filter(Q(end_date__isnull=True) | Q(end_date__gte=start_date)))
    if selected_project_id:
        planned_allocations = planned_allocations.filter(project_id=selected_project_id)
    if selected_resource_id:
        planned_allocations = planned_allocations.filter(resource_id=selected_resource_id)

    total_demand_hours = _ZERO
    for alloc in planned_allocations:
        total_demand_hours += alloc.planned_hours(start_date, end_date)

    capacity_demand_summary = {
        "capacity_hours": q2(total_capacity_month),
        "demand_hours": q2(total_demand_hours),
        "actual_hours": q2(total_hours),
        "billable_hours": q2(billable_hours),
        "variance_actual_vs_demand": q2(total_hours - total_demand_hours),
    }

    months_choices = [
        (1, "January"), (2, "February"), (3, "March"), (4, "April"),
        (5, "May"), (6, "June"), (7, "July"), (8, "August"),
        (9, "September"), (10, "October"), (11, "November"), (12, "December")
    ]
    years_choices = list(range(today.year - 2, today.year + 3))

    context = {
        "year": year,
        "month": month,
        "month_name": date(year, month, 1).strftime("%B"),
        "months_choices": months_choices,
        "years_choices": years_choices,
        "projects": projects(tenant),
        "resources": resource_profiles(tenant),
        "selected_project": selected_project_id,
        "selected_resource": selected_resource_id,
        "kpi": {
            "total_hours": q2(total_hours),
            "billable_hours": q2(billable_hours),
            "non_billable_hours": q2(non_billable_hours),
            "overtime_hours": q2(total_overtime_hours),
            "chargeability_ratio": chargeability_ratio,
            "overall_utilization": overall_utilization,
        },
        "individual_rows": individual_rows,
        "client_splits": client_splits,
        "overhead_splits": overhead_splits,
        "capacity_demand": capacity_demand_summary,
    }
    return render(request, "projects/timeattendance/utilization/dashboard.html", context)
