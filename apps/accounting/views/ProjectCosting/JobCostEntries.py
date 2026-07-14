"""Accounting 2.9 Project/Job Costing — JobCostEntries views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _post_journal_entry
from apps.accounting.models import (
    JobCostEntry,
    Project,
    ZERO,
)
from apps.accounting.forms import (
    JobCostEntryForm,
)


# --------------------------------------------------------------- Job cost entries
@login_required
def job_cost_entry_list(request):
    return crud_list(
        request, JobCostEntry.objects.filter(tenant=request.tenant).select_related("project", "gl_account"),
        "accounting/projects/job_cost_entry/list.html",
        search_fields=["number", "description", "project__name"],
        filters=[("status", "status", False), ("kind", "kind", False), ("project", "project_id", True)],
        extra_context={"status_choices": JobCostEntry.STATUS_CHOICES, "kind_choices": JobCostEntry.KIND_CHOICES,
                       "projects": Project.objects.filter(tenant=request.tenant)},
    )


@login_required
def job_cost_entry_create(request):
    return crud_create(request, form_class=JobCostEntryForm, template="accounting/projects/job_cost_entry/form.html",
                       success_url="accounting:job_cost_entry_list")


@login_required
def job_cost_entry_detail(request, pk):
    obj = get_object_or_404(JobCostEntry.objects.select_related("project", "gl_account", "journal_entry"),
                            pk=pk, tenant=request.tenant)
    return render(request, "accounting/projects/job_cost_entry/detail.html", {"obj": obj})


@login_required
def job_cost_entry_edit(request, pk):
    entry = get_object_or_404(JobCostEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "A posted cost entry cannot be edited.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    return crud_edit(request, model=JobCostEntry, pk=pk, form_class=JobCostEntryForm,
                     template="accounting/projects/job_cost_entry/form.html", success_url="accounting:job_cost_entry_list")


@login_required
@require_POST
def job_cost_entry_delete(request, pk):
    entry = get_object_or_404(JobCostEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "A posted cost entry cannot be deleted.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    return crud_delete(request, model=JobCostEntry, pk=pk, success_url="accounting:job_cost_entry_list")


@tenant_admin_required
@require_POST
def job_cost_entry_post(request, pk):
    entry = get_object_or_404(JobCostEntry.objects.select_related("project", "gl_account"),
                              pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "This cost entry is already posted.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    cash = _first_account(request.tenant, "asset", "1000") or _first_account(request.tenant, "asset")
    if not (entry.gl_account and cash) or (entry.amount or ZERO) <= ZERO:
        messages.error(request, "A GL account, a cash account and a positive amount are required to post.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    org = entry.project.org_unit if entry.project_id else None
    if entry.kind == "cost":  # Dr expense / Cr cash
        legs = [(entry.gl_account, entry.amount, ZERO, None, org), (cash, ZERO, entry.amount, None, org)]
    else:  # revenue: Dr cash / Cr income
        legs = [(cash, entry.amount, ZERO, None, org), (entry.gl_account, ZERO, entry.amount, None, org)]
    with transaction.atomic():
        je = _post_journal_entry(request.tenant, request.user,
                                 f"{entry.get_kind_display()} — {entry.project.name} ({entry.number})", legs,
                                 reference=entry.number)
        if je is None:
            messages.error(request, "Cost entry did not balance — nothing was posted.")
            return redirect("accounting:job_cost_entry_detail", pk=pk)
        entry.journal_entry = je
        entry.status = "posted"
        entry.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, entry, "update", {"action": "post"})
    messages.success(request, f"Cost entry {entry.number} posted.")
    return redirect("accounting:job_cost_entry_detail", pk=pk)
