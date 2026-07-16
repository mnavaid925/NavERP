"""HRM 3.11 Time Tracking — Timesheet views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Timesheet,
    TimesheetEntry,
)
from apps.hrm.forms import (
    TimesheetEntryForm,
    TimesheetForm,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


# ============================================================ Timesheets (3.11)
@login_required
def timesheet_list(request):
    qs = (Timesheet.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "approver"))
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if date_from:
        qs = qs.filter(period_start__gte=date_from)
    if date_to:
        qs = qs.filter(period_start__lte=date_to)
    return crud_list(
        request, qs, "hrm/timetracking/timesheet/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True)],
        extra_context={"status_choices": Timesheet.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def timesheet_create(request):
    return crud_create(request, form_class=TimesheetForm, template="hrm/timetracking/timesheet/form.html",
                       success_url="hrm:timesheet_list")


@login_required
def timesheet_detail(request, pk):
    obj = get_object_or_404(
        Timesheet.objects.select_related("employee__party", "approver"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/timetracking/timesheet/detail.html", {
        "obj": obj,
        "entries": obj.entries.select_related("project").order_by("date"),
        "entry_form": TimesheetEntryForm(tenant=request.tenant),
        "can_edit_entries": obj.status in Timesheet.OPEN_STATUSES,
    })


@login_required
def timesheet_edit(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending timesheet can be edited.")
        return redirect("hrm:timesheet_detail", pk=obj.pk)
    return crud_edit(request, model=Timesheet, pk=pk, form_class=TimesheetForm,
                     template="hrm/timetracking/timesheet/form.html", success_url="hrm:timesheet_list")


@login_required
@require_POST
def timesheet_delete(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "A decided timesheet cannot be deleted — cancel it instead.")
        return redirect("hrm:timesheet_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Timesheet deleted.")
    return redirect("hrm:timesheet_list")


@login_required
@require_POST
def timesheet_submit(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Timesheet {obj.number} submitted for approval.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


@tenant_admin_required  # approving a timesheet is a privileged manager/admin action
@require_POST
def timesheet_approve(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.refresh_totals(save=False)  # final recompute of the derived totals before locking
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "approved_at", "decision_note",
                                "total_hours", "billable_hours", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve", "total_hours": str(obj.total_hours)})
        messages.success(request, f"Timesheet {obj.number} approved.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


@tenant_admin_required  # rejecting a timesheet is a privileged manager/admin action
@require_POST
def timesheet_reject(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.rejected_reason = request.POST.get("rejected_reason", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "rejected_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Timesheet {obj.number} rejected.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


@login_required
@require_POST
def timesheet_cancel(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Timesheet {obj.number} cancelled.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


# --- TimesheetEntry: inline child rows managed on the timesheet hub (locked once approved) ---
@login_required
@require_POST
def timesheetentry_add(request, ts_pk):
    ts = get_object_or_404(Timesheet, pk=ts_pk, tenant=request.tenant)
    if ts.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Cannot modify entries on a decided timesheet.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    # Preset tenant+timesheet on the instance so the model clean()'s date-in-period check runs on validate.
    form = TimesheetEntryForm(request.POST,
                              instance=TimesheetEntry(tenant=request.tenant, timesheet=ts),
                              tenant=request.tenant)
    if form.is_valid():
        form.save()
        ts.refresh_totals()
        write_audit_log(request.user, ts, "update", {"action": "entry_add"})
        messages.success(request, "Entry added.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    # Re-render the hub with the bound, errored add-form so field errors + typed input are preserved.
    return render(request, "hrm/timetracking/timesheet/detail.html", {
        "obj": ts,
        "entries": ts.entries.select_related("project").order_by("date"),
        "entry_form": form,
        "can_edit_entries": True,
    })
