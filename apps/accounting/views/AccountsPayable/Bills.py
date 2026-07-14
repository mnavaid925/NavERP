"""Accounting 2.3 Accounts Payable — Bills views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _need_tenant
from apps.accounting.models import (
    Bill,
)
from apps.accounting.forms import (
    BillForm,
    BillLineFormSet,
)


def _vendor_parties(tenant):
    return Party.objects.filter(tenant=tenant, roles__role="vendor").distinct()


# ======================================================================= 2.3 AP — Bills
@login_required
def bill_list(request):
    return crud_list(
        request, Bill.objects.filter(tenant=request.tenant).select_related("party", "currency"),
        "accounting/payable/bill/list.html",
        search_fields=["number", "party__name"],
        filters=[("status", "status", False), ("party", "party_id", True)],
        extra_context={"status_choices": Bill.STATUS_CHOICES, "parties": _vendor_parties(request.tenant)},
    )


@login_required
def bill_create(request):
    return _bill_form(request, instance=None)


@login_required
def bill_edit(request, pk):
    bill = get_object_or_404(Bill, pk=pk, tenant=request.tenant)
    if bill.is_locked:
        messages.error(request, "A paid or void bill cannot be edited.")
        return redirect("accounting:bill_detail", pk=pk)
    return _bill_form(request, instance=bill)


def _bill_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("accounting:bill_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = BillForm(request.POST, request.FILES, instance=instance, tenant=request.tenant)
        formset = BillLineFormSet(request.POST, instance=instance, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                bill = form.save(commit=False)
                bill.tenant = request.tenant
                bill.save()
                formset.instance = bill
                formset.save()
                bill.recalc_totals()
            write_audit_log(request.user, bill, "update" if is_edit else "create")
            messages.success(request, f"Bill {bill.number} saved.")
            return redirect("accounting:bill_detail", pk=bill.pk)
    else:
        form = BillForm(instance=instance, tenant=request.tenant)
        formset = BillLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "accounting/payable/bill/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def bill_detail(request, pk):
    obj = get_object_or_404(
        Bill.objects.select_related("party", "payment_terms", "currency", "approved_by", "document"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounting/payable/bill/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("gl_account"),
        "allocations": obj.allocations.select_related("payment"),
        "amount_paid": obj.amount_paid(),
        "balance_due": obj.balance_due(),
    })


@login_required
@require_POST
def bill_delete(request, pk):
    bill = get_object_or_404(Bill, pk=pk, tenant=request.tenant)
    if bill.status != "draft":
        messages.error(request, "Only a draft bill can be deleted.")
        return redirect("accounting:bill_detail", pk=pk)
    return crud_delete(request, model=Bill, pk=pk, success_url="accounting:bill_list")


@tenant_admin_required
@require_POST
def bill_approve(request, pk):
    bill = get_object_or_404(Bill, pk=pk, tenant=request.tenant)
    if bill.status not in ("draft", "pending_approval"):
        messages.info(request, "This bill is not awaiting approval.")
        return redirect("accounting:bill_detail", pk=pk)
    bill.status = "approved"
    bill.approved_by = request.user
    bill.save(update_fields=["status", "approved_by", "updated_at"])
    write_audit_log(request.user, bill, "update", {"action": "approve"})
    messages.success(request, f"Bill {bill.number} approved.")
    return redirect("accounting:bill_detail", pk=pk)
