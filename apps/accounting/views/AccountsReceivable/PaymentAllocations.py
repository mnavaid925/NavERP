"""Accounting 2.4 Accounts Receivable — PaymentAllocations views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _need_tenant, _recompute_doc_status
from apps.accounting.models import (
    Payment,
    PaymentAllocation,
)
from apps.accounting.forms import (
    PaymentAllocationForm,
)


# ---------------------------------------------------- Payment allocations (cash application)
@login_required
def allocation_list(request):
    return crud_list(
        request, PaymentAllocation.objects.filter(payment__tenant=request.tenant)
        .select_related("payment", "invoice", "bill"),
        "accounting/receivable/allocation/list.html",
        search_fields=["payment__number", "invoice__number", "bill__number"],
        filters=[("payment", "payment_id", True)],
        extra_context={"payments": Payment.objects.filter(tenant=request.tenant)},
    )


@login_required
def allocation_create(request):
    if _need_tenant(request):
        return redirect("accounting:allocation_list")
    if request.method == "POST":
        form = PaymentAllocationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            _recompute_doc_status(obj.invoice, obj.bill)
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Allocation created.")
            return redirect("accounting:allocation_list")
    else:
        form = PaymentAllocationForm(tenant=request.tenant)
    return render(request, "accounting/receivable/allocation/form.html", {"form": form, "is_edit": False})


@login_required
def allocation_detail(request, pk):
    obj = get_object_or_404(
        PaymentAllocation.objects.select_related("payment", "invoice", "bill"),
        pk=pk, payment__tenant=request.tenant,
    )
    return render(request, "accounting/receivable/allocation/detail.html", {"obj": obj})


@login_required
def allocation_edit(request, pk):
    obj = get_object_or_404(PaymentAllocation, pk=pk, payment__tenant=request.tenant)
    if request.method == "POST":
        form = PaymentAllocationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            _recompute_doc_status(obj.invoice, obj.bill)
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Allocation updated.")
            return redirect("accounting:allocation_list")
    else:
        form = PaymentAllocationForm(instance=obj, tenant=request.tenant)
    return render(request, "accounting/receivable/allocation/form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def allocation_delete(request, pk):
    obj = get_object_or_404(PaymentAllocation, pk=pk, payment__tenant=request.tenant)
    invoice, bill = obj.invoice, obj.bill
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    _recompute_doc_status(invoice, bill)
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:allocation_list")
