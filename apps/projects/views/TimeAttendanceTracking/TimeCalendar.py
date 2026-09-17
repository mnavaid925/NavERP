"""Projects 7.11 — Time & Attendance Calendar Sync (Bullet 4).

Calendar visualization synchronizing project time logs, approved leaves (hrm.LeaveRequest),
public holidays (hrm.PublicHoliday), and project overtime records.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.db.models import Sum

from apps.core.crud import as_db_int
from apps.projects.models import (
    ProjectOvertimeRecord, ResourceProfile, ResourceTimeEntry)
from apps.projects.models._base import q2
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render, timezone
from apps.projects.views._helpers import projects, resource_profiles

_ZERO = Decimal("0")


@login_required
def time_calendar(request):
    tenant = request.tenant
    today = timezone.localdate()

    year = as_db_int(request.GET.get("year")) or today.year
    month = as_db_int(request.GET.get("month")) or today.month
    if not (1 <= month <= 12):
        month = today.month
    if not (2000 <= year <= 2100):
        year = today.year

    selected_project_id = as_db_int(request.GET.get("project"))
    selected_resource_id = as_db_int(request.GET.get("resource"))

    first_day = date(year, month, 1)
    num_days = calendar.monthrange(year, month)[1]
    last_day = date(year, month, num_days)

    entries_qs = ResourceTimeEntry.objects.filter(
        tenant=tenant,
        entry_date__gte=first_day,
        entry_date__lte=last_day,
    ).select_related("resource__employee__party", "resource__party", "project")
    if selected_project_id:
        entries_qs = entries_qs.filter(project_id=selected_project_id)
    if selected_resource_id:
        entries_qs = entries_qs.filter(resource_id=selected_resource_id)

    daily_entries = {}
    for e in entries_qs:
        d = e.entry_date.day
        if d not in daily_entries:
            daily_entries[d] = {"hours": _ZERO, "billable_hours": _ZERO, "count": 0, "entries": []}
        daily_entries[d]["hours"] += e.hours
        if e.is_billable:
            daily_entries[d]["billable_hours"] += e.hours
        daily_entries[d]["count"] += 1
        daily_entries[d]["entries"].append(e)

    ot_qs = ProjectOvertimeRecord.objects.filter(
        tenant=tenant,
        date__gte=first_day,
        date__lte=last_day,
    ).select_related("resource__employee__party", "resource__party", "project")
    if selected_project_id:
        ot_qs = ot_qs.filter(project_id=selected_project_id)
    if selected_resource_id:
        ot_qs = ot_qs.filter(resource_id=selected_resource_id)

    daily_overtime = {}
    for ot in ot_qs:
        d = ot.date.day
        if d not in daily_overtime:
            daily_overtime[d] = {"hours": _ZERO, "records": []}
        daily_overtime[d]["hours"] += ot.overtime_hours
        daily_overtime[d]["records"].append(ot)

    daily_holidays = {}
    if apps.is_installed("apps.hrm"):
        try:
            from apps.hrm.models import PublicHoliday
            holidays = PublicHoliday.objects.filter(
                tenant=tenant,
                date__gte=first_day,
                date__lte=last_day,
            )
            for h in holidays:
                d = h.date.day
                if d not in daily_holidays:
                    daily_holidays[d] = []
                daily_holidays[d].append(h)
        except Exception:
            pass

    daily_leaves = {}
    if apps.is_installed("apps.hrm"):
        try:
            from apps.hrm.models import LeaveRequest
            leaves = LeaveRequest.objects.filter(
                tenant=tenant,
                status="approved",
                start_date__lte=last_day,
                end_date__gte=first_day,
            ).select_related("employee__party", "leave_type")
            for lv in leaves:
                lv_start = max(lv.start_date, first_day)
                lv_end = min(lv.end_date, last_day)
                curr = lv_start
                while curr <= lv_end:
                    d = curr.day
                    if d not in daily_leaves:
                        daily_leaves[d] = []
                    daily_leaves[d].append(lv)
                    curr += timezone.timedelta(days=1)
        except Exception:
            pass

    cal = calendar.Calendar(firstweekday=0)
    month_weeks = []
    month_total_hours = _ZERO
    month_total_ot = _ZERO

    for week in cal.monthdatescalendar(year, month):
        week_days = []
        for d in week:
            is_current_month = (d.month == month)
            day_num = d.day if is_current_month else None
            time_data = daily_entries.get(day_num, {"hours": _ZERO, "billable_hours": _ZERO, "count": 0, "entries": []}) if is_current_month else None
            ot_data = daily_overtime.get(day_num, {"hours": _ZERO, "records": []}) if is_current_month else None
            hols = daily_holidays.get(day_num, []) if is_current_month else []
            leaves = daily_leaves.get(day_num, []) if is_current_month else []

            is_weekend = (d.weekday() in (5, 6))
            is_today = (d == today)

            if is_current_month and time_data:
                month_total_hours += time_data["hours"]
            if is_current_month and ot_data:
                month_total_ot += ot_data["hours"]

            week_days.append({
                "date": d,
                "day_num": d.day,
                "is_current_month": is_current_month,
                "is_weekend": is_weekend,
                "is_today": is_today,
                "time_data": time_data,
                "ot_data": ot_data,
                "holidays": hols,
                "leaves": leaves,
                "has_conflict": (time_data and time_data["hours"] > _ZERO and (hols or leaves)),
            })
        month_weeks.append(week_days)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

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
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
        "months_choices": months_choices,
        "years_choices": years_choices,
        "projects": projects(tenant),
        "resources": resource_profiles(tenant),
        "selected_project": selected_project_id,
        "selected_resource": selected_resource_id,
        "month_weeks": month_weeks,
        "month_total_hours": q2(month_total_hours),
        "month_total_ot": q2(month_total_ot),
    }
    return render(request, "projects/timeattendance/calendar/calendar.html", context)
