"""Accounting 2.7 Inventory & Cost Management — CostAllocations views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _post_journal_entry
from apps.accounting.models import (
    CostAllocation,
    ZERO,
)
from apps.accounting.forms import (
    CostAllocationForm,
)


# ====================================================== 2.7 Cost Allocation
@login_required
def cost_allocation_list(request):
    return crud_list(
        request, CostAllocation.objects.filter(tenant=request.tenant)
        .select_related("source_account", "target_account", "target_org_unit"),
        "accounting/costing/cost_allocation/list.html",
        search_fields=["number", "description"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": CostAllocation.STATUS_CHOICES},
    )


@login_required
def cost_allocation_create(request):
    return crud_create(request, form_class=CostAllocationForm, template="accounting/costing/cost_allocation/form.html",
                       success_url="accounting:cost_allocation_list")


@login_required
def cost_allocation_detail(request, pk):
    obj = get_object_or_404(
        CostAllocation.objects.select_related("source_account", "target_account", "target_org_unit", "journal_entry"),
        pk=pk, tenant=request.tenant)
    return render(request, "accounting/costing/cost_allocation/detail.html", {"obj": obj})


@login_required
def cost_allocation_edit(request, pk):
    alloc = get_object_or_404(CostAllocation, pk=pk, tenant=request.tenant)
    if alloc.is_locked:
        messages.error(request, "A posted allocation cannot be edited.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    return crud_edit(request, model=CostAllocation, pk=pk, form_class=CostAllocationForm,
                     template="accounting/costing/cost_allocation/form.html", success_url="accounting:cost_allocation_list")


@login_required
@require_POST
def cost_allocation_delete(request, pk):
    alloc = get_object_or_404(CostAllocation, pk=pk, tenant=request.tenant)
    if alloc.is_locked:
        messages.error(request, "A posted allocation cannot be deleted.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    return crud_delete(request, model=CostAllocation, pk=pk, success_url="accounting:cost_allocation_list")


@tenant_admin_required
@require_POST
def cost_allocation_post(request, pk):
    alloc = get_object_or_404(CostAllocation.objects.select_related("source_account", "target_account", "target_org_unit"),
                              pk=pk, tenant=request.tenant)
    if alloc.is_locked:
        messages.error(request, "This allocation is already posted.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    if (alloc.amount or ZERO) <= ZERO:
        messages.error(request, "Allocation amount must be greater than zero.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    with transaction.atomic():
        je = _post_journal_entry(
            request.tenant, request.user, f"Cost allocation {alloc.number} — {alloc.description}",
            [(alloc.target_account, alloc.amount, ZERO, None, alloc.target_org_unit),
             (alloc.source_account, ZERO, alloc.amount, None, None)], reference=alloc.number)
        if je is None:
            messages.error(request, "Allocation entry did not balance — nothing was posted.")
            return redirect("accounting:cost_allocation_detail", pk=pk)
        alloc.journal_entry = je
        alloc.status = "posted"
        alloc.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, alloc, "update", {"action": "post"})
    messages.success(request, f"Allocation {alloc.number} posted.")
    return redirect("accounting:cost_allocation_detail", pk=pk)
