"""HRM 3.17 Payout & Reports — Bankreconciliation views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    BankReconciliation,
    PayoutBatch,
)
from apps.hrm.forms import (
    BankReconciliationForm,
)


# ---------------------------------------------------------- BankReconciliation
@login_required
def bankreconciliation_list(request):
    return crud_list(
        request,
        # List renders only batch.number — no batch__cycle join (detail keeps it, where cycle IS shown).
        BankReconciliation.objects.filter(tenant=request.tenant).select_related("batch"),
        "hrm/payout/bankreconciliation/list.html",
        search_fields=["number", "batch__number", "statement_reference"],
        filters=[("status", "status", False), ("batch", "batch_id", True)],
        extra_context={
            "status_choices": BankReconciliation.STATUS_CHOICES,
            "batches": PayoutBatch.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def bankreconciliation_create(request):
    return crud_create(request, form_class=BankReconciliationForm,
                       template="hrm/payout/bankreconciliation/form.html",
                       success_url="hrm:bankreconciliation_list")


@login_required
def bankreconciliation_detail(request, pk):
    obj = get_object_or_404(
        BankReconciliation.objects.select_related("batch__cycle", "reconciled_by"),
        pk=pk, tenant=request.tenant)
    exceptions = (obj.batch._current_payments().filter(status__in=["failed", "returned"])
                  .select_related("employee__party"))
    return render(request, "hrm/payout/bankreconciliation/detail.html",
                  {"obj": obj, "exceptions": exceptions})


@login_required
def bankreconciliation_edit(request, pk):
    obj = get_object_or_404(BankReconciliation, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "A reconciled/closed reconciliation can no longer be edited.")
        return redirect("hrm:bankreconciliation_detail", pk=obj.pk)
    return crud_edit(request, model=BankReconciliation, pk=pk, form_class=BankReconciliationForm,
                     template="hrm/payout/bankreconciliation/form.html",
                     success_url="hrm:bankreconciliation_list")


@login_required
@require_POST
def bankreconciliation_delete(request, pk):
    obj = get_object_or_404(BankReconciliation, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "A reconciled/closed reconciliation can no longer be deleted.")
        return redirect("hrm:bankreconciliation_detail", pk=obj.pk)
    return crud_delete(request, model=BankReconciliation, pk=pk, success_url="hrm:bankreconciliation_list")


@tenant_admin_required
@require_POST
def bankreconciliation_reconcile(request, pk):
    recon = get_object_or_404(
        BankReconciliation.objects.select_related("batch"), pk=pk, tenant=request.tenant)
    recon.recompute()  # sets matched/unmatched + status + reconciled_at
    recon.reconciled_by = request.user
    recon.save(update_fields=["reconciled_by", "updated_at"])
    # On a full match, flip the batch itself to reconciled (batch-level only, no payment changes).
    if recon.status == "reconciled" and recon.batch.status in ("disbursed", "partially_disbursed"):
        recon.batch.status = "reconciled"
        recon.batch.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, recon, "update", {"action": "reconcile", "status": recon.status})
    messages.success(request,
        f"Reconciliation {recon.number}: {recon.matched_count} matched, {recon.unmatched_count} "
        f"unmatched ({recon.get_status_display()}).")
    return redirect("hrm:bankreconciliation_detail", pk=recon.pk)
