"""Accounting 2.10 Multi-Entity & Consolidation — IntercompanyTransactions views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _post_journal_entry
from apps.accounting.models import (
    IntercompanyTransaction,
    ZERO,
)
from apps.accounting.forms import (
    IntercompanyTransactionForm,
)


# ============================================== 2.10 Multi-Entity / Intercompany
@login_required
def intercompany_list(request):
    return crud_list(
        request, IntercompanyTransaction.objects.filter(tenant=request.tenant)
        .select_related("from_org_unit", "to_org_unit"),
        "accounting/intercompany/list.html",
        search_fields=["number", "description"],
        filters=[("status", "status", False), ("eliminated", "eliminated", False)],
        extra_context={"status_choices": IntercompanyTransaction.STATUS_CHOICES},
    )


@login_required
def intercompany_create(request):
    return crud_create(request, form_class=IntercompanyTransactionForm, template="accounting/intercompany/form.html",
                       success_url="accounting:intercompany_list")


@login_required
def intercompany_detail(request, pk):
    obj = get_object_or_404(
        IntercompanyTransaction.objects.select_related("from_org_unit", "to_org_unit", "due_from_account",
                                                       "due_to_account", "journal_entry"),
        pk=pk, tenant=request.tenant)
    return render(request, "accounting/intercompany/detail.html", {"obj": obj})


@login_required
def intercompany_edit(request, pk):
    ict = get_object_or_404(IntercompanyTransaction, pk=pk, tenant=request.tenant)
    if ict.is_locked:
        messages.error(request, "A posted intercompany transaction cannot be edited.")
        return redirect("accounting:intercompany_detail", pk=pk)
    return crud_edit(request, model=IntercompanyTransaction, pk=pk, form_class=IntercompanyTransactionForm,
                     template="accounting/intercompany/form.html", success_url="accounting:intercompany_list")


@login_required
@require_POST
def intercompany_delete(request, pk):
    ict = get_object_or_404(IntercompanyTransaction, pk=pk, tenant=request.tenant)
    if ict.is_locked:
        messages.error(request, "A posted intercompany transaction cannot be deleted.")
        return redirect("accounting:intercompany_detail", pk=pk)
    return crud_delete(request, model=IntercompanyTransaction, pk=pk, success_url="accounting:intercompany_list")


@tenant_admin_required
@require_POST
def intercompany_post(request, pk):
    ict = get_object_or_404(
        IntercompanyTransaction.objects.select_related("from_org_unit", "to_org_unit", "due_from_account",
                                                       "due_to_account"),
        pk=pk, tenant=request.tenant)
    if ict.is_locked:
        messages.error(request, "This intercompany transaction is already posted.")
        return redirect("accounting:intercompany_detail", pk=pk)
    due_from = ict.due_from_account or _first_account(request.tenant, "asset", "1100") \
        or _first_account(request.tenant, "asset")
    due_to = ict.due_to_account or _first_account(request.tenant, "liability", "2000") \
        or _first_account(request.tenant, "liability")
    if not (due_from and due_to) or (ict.amount or ZERO) <= ZERO:
        messages.error(request, "Due-from and due-to accounts and a positive amount are required to post.")
        return redirect("accounting:intercompany_detail", pk=pk)
    with transaction.atomic():
        # due-from (receivable) sits on the lender's books (from_org_unit); due-to (payable) on the
        # borrower's books (to_org_unit).
        je = _post_journal_entry(
            request.tenant, request.user, f"Intercompany {ict.number} — {ict.description}",
            [(due_from, ict.amount, ZERO, None, ict.from_org_unit),
             (due_to, ZERO, ict.amount, None, ict.to_org_unit)], reference=ict.number)
        if je is None:
            messages.error(request, "Intercompany transaction did not balance — nothing was posted.")
            return redirect("accounting:intercompany_detail", pk=pk)
        ict.journal_entry = je
        ict.status = "posted"
        ict.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, ict, "update", {"action": "post"})
    messages.success(request, f"Intercompany transaction {ict.number} posted.")
    return redirect("accounting:intercompany_detail", pk=pk)


@tenant_admin_required
@require_POST
def intercompany_toggle_eliminated(request, pk):
    ict = get_object_or_404(IntercompanyTransaction, pk=pk, tenant=request.tenant)
    ict.eliminated = not ict.eliminated
    ict.save(update_fields=["eliminated", "updated_at"])
    write_audit_log(request.user, ict, "update", {"action": "toggle_eliminated", "eliminated": ict.eliminated})
    messages.success(request, f"Marked {'eliminated' if ict.eliminated else 'not eliminated'} for consolidation.")
    return redirect("accounting:intercompany_detail", pk=pk)
