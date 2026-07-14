"""Accounting 2.5 Cash Management — Reconciliation views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    ReconciliationMatch,
)
from apps.accounting.forms import (
    ReconciliationMatchForm,
)


# ============================================================== 2.5 Cash — Reconciliation
@login_required
def reconciliation_list(request):
    return crud_list(
        request, ReconciliationMatch.objects.filter(tenant=request.tenant)
        .select_related("bank_transaction", "payment", "matched_by"),
        "accounting/cash/reconciliation/list.html",
        search_fields=["bank_transaction__description"],
        filters=[("is_confirmed", "is_confirmed", False)],
    )


@login_required
def reconciliation_create(request):
    return crud_create(request, form_class=ReconciliationMatchForm, template="accounting/cash/reconciliation/form.html",
                       success_url="accounting:reconciliation_list")


@login_required
def reconciliation_detail(request, pk):
    obj = get_object_or_404(
        ReconciliationMatch.objects.select_related(
            "bank_transaction", "payment", "journal_line", "journal_line__entry", "matched_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounting/cash/reconciliation/detail.html", {"obj": obj})


@login_required
def reconciliation_edit(request, pk):
    return crud_edit(request, model=ReconciliationMatch, pk=pk, form_class=ReconciliationMatchForm,
                     template="accounting/cash/reconciliation/form.html", success_url="accounting:reconciliation_list")


@login_required
@require_POST
def reconciliation_delete(request, pk):
    return crud_delete(request, model=ReconciliationMatch, pk=pk, success_url="accounting:reconciliation_list")


@tenant_admin_required
@require_POST
def reconciliation_confirm(request, pk):
    match = get_object_or_404(ReconciliationMatch, pk=pk, tenant=request.tenant)
    match.is_confirmed = not match.is_confirmed
    if match.matched_by_id is None:
        match.matched_by = request.user
    match.save(update_fields=["is_confirmed", "matched_by", "updated_at"])
    txn = match.bank_transaction
    txn.status = "reconciled" if match.is_confirmed else "matched"
    txn.save(update_fields=["status"])
    write_audit_log(request.user, match, "update", {"action": "reconcile", "confirmed": match.is_confirmed})
    messages.success(request, "Reconciliation updated.")
    return redirect("accounting:reconciliation_detail", pk=pk)
