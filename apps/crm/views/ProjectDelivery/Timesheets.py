"""CRM 1.8 Project & Delivery Management — Timesheets views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmProject,
    Timesheet,
)
from apps.crm.forms import (
    TimesheetForm,
)


# ------------------------------------------------------------ 1.8 Timesheets
@login_required
def timesheet_list(request):
    return crud_list(
        request,
        Timesheet.objects.filter(tenant=request.tenant).select_related(
            "project", "employee", "milestone", "client"),
        "crm/projects/timesheet/list.html",
        search_fields=["number", "description", "employee__username"],
        filters=[("status", "status", False), ("project", "project_id", True),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": Timesheet.STATUS_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": User.objects.filter(tenant=request.tenant).order_by("username")},
    )


@login_required
def timesheet_create(request):
    return crud_create(request, form_class=TimesheetForm, template="crm/projects/timesheet/form.html",
                       success_url="crm:timesheet_list")


@login_required
def timesheet_detail(request, pk):
    obj = get_object_or_404(
        Timesheet.objects.select_related("project", "employee", "milestone", "client", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/projects/timesheet/detail.html", {"obj": obj})


@login_required
def timesheet_edit(request, pk):
    # Lock down post-approval edits: once submitted/approved, the hours an approval was granted for
    # must not be silently mutated (code-review). Re-open by rejecting first.
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected timesheet can be edited.")
        return redirect("crm:timesheet_detail", pk=obj.pk)
    return crud_edit(request, model=Timesheet, pk=pk, form_class=TimesheetForm,
                     template="crm/projects/timesheet/form.html", success_url="crm:timesheet_list")


@login_required
@require_POST
def timesheet_delete(request, pk):
    # An approved (audited) timesheet must not be silently erased; only draft/rejected are deletable
    # (the template hides the button for other states — guard the view too) (security-review).
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected timesheet can be deleted.")
        return redirect("crm:timesheet_detail", pk=obj.pk)
    return crud_delete(request, model=Timesheet, pk=pk, success_url="crm:timesheet_list")


# ---- 1.8 Timesheet approval workflow (status off the form — advanced only here) ----------
@login_required
@require_POST
def timesheet_submit(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    # Only the time logger (or an admin) may submit it — not an arbitrary colleague (security-review).
    if not (obj.employee_id == request.user.pk or request.user.is_superuser
            or request.user.is_tenant_admin):
        messages.error(request, "You can only submit your own timesheet.")
        return redirect("crm:timesheet_detail", pk=obj.pk)
    if obj.status == "draft":
        obj.status = "submitted"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Timesheet {obj.number} submitted for approval.")
    return redirect("crm:timesheet_detail", pk=obj.pk)


@tenant_admin_required  # approving is privileged — a manager/admin, not the time logger
@require_POST
def timesheet_approve(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.save(update_fields=["status", "approved_by", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Timesheet {obj.number} approved.")
    return redirect("crm:timesheet_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def timesheet_reject(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    obj.status = "rejected"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Timesheet {obj.number} rejected.")
    return redirect("crm:timesheet_detail", pk=obj.pk)
