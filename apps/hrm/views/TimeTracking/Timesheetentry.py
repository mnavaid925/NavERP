"""HRM 3.11 Time Tracking — Timesheetentry views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Timesheet,
    TimesheetEntry,
)
from apps.hrm.forms import (
    TimesheetEntryForm,
)


@login_required
def timesheetentry_edit(request, pk):
    entry = get_object_or_404(TimesheetEntry.objects.select_related("timesheet"), pk=pk, tenant=request.tenant)
    ts = entry.timesheet
    if ts.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Cannot modify entries on a decided timesheet.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    if request.method == "POST":
        form = TimesheetEntryForm(request.POST, instance=entry, tenant=request.tenant)
        if form.is_valid():
            form.save()
            ts.refresh_totals()
            write_audit_log(request.user, ts, "update", {"action": "entry_edit"})
            messages.success(request, "Entry updated.")
            return redirect("hrm:timesheet_detail", pk=ts.pk)
    else:
        form = TimesheetEntryForm(instance=entry, tenant=request.tenant)
    return render(request, "hrm/timetracking/timesheetentry/form.html",
                  {"form": form, "obj": entry, "timesheet": ts, "is_edit": True})


@login_required
@require_POST
def timesheetentry_delete(request, pk):
    entry = get_object_or_404(TimesheetEntry.objects.select_related("timesheet"), pk=pk, tenant=request.tenant)
    ts = entry.timesheet
    if ts.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Cannot modify entries on a decided timesheet.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    entry.delete()
    ts.refresh_totals()
    write_audit_log(request.user, ts, "update", {"action": "entry_delete"})
    messages.success(request, "Entry removed.")
    return redirect("hrm:timesheet_detail", pk=ts.pk)
