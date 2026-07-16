"""HRM 3.17 Payout & Reports — Payoutpayments views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PayoutReports._helpers import _recompute_batch_status
from apps.hrm.models import (
    PayoutPayment,
)
from apps.hrm.views.PayoutReports._helpers import _recompute_batch_status


# ---------------------------------------------------------- PayoutPayment actions
@tenant_admin_required
@require_POST
def payoutpayment_mark_paid(request, pk):
    payment = get_object_or_404(PayoutPayment.objects.select_related("batch"), pk=pk, tenant=request.tenant)
    if payment.status not in ("pending", "processing"):
        messages.error(request, "Only a pending/processing payment can be marked paid.")
        return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)
    payment.status = "paid"
    payment.paid_on = timezone.now()
    payment.transaction_reference = request.POST.get("transaction_reference", "").strip()[:64]
    with transaction.atomic():
        payment.save(update_fields=["status", "paid_on", "transaction_reference", "updated_at"])
        _recompute_batch_status(payment.batch)
    write_audit_log(request.user, payment, "update", {"action": "mark_paid"})
    messages.success(request, "Payment marked paid.")
    return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)


@tenant_admin_required
@require_POST
def payoutpayment_mark_failed(request, pk):
    payment = get_object_or_404(PayoutPayment.objects.select_related("batch"), pk=pk, tenant=request.tenant)
    if payment.status not in ("pending", "processing"):
        messages.error(request, "Only a pending/processing payment can be marked failed.")
        return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)
    payment.status = "failed"
    payment.failure_reason = request.POST.get("failure_reason", "").strip()[:2000]
    with transaction.atomic():
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        _recompute_batch_status(payment.batch)
    write_audit_log(request.user, payment, "update", {"action": "mark_failed"})
    messages.success(request, "Payment marked failed.")
    return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)


@tenant_admin_required
@require_POST
def payoutpayment_retry(request, pk):
    """Re-initiate a failed/returned payment as a NEW row (retry_of → the original, preserving history),
    re-snapshotting the employee's CURRENT bank details (in case they were corrected)."""
    original = get_object_or_404(
        PayoutPayment.objects.select_related("batch", "employee"), pk=pk, tenant=request.tenant)
    if original.status not in ("failed", "returned"):
        messages.error(request, "Only a failed/returned payment can be retried.")
        return redirect("hrm:payoutbatch_detail", pk=original.batch_id)
    emp = original.employee
    with transaction.atomic():
        PayoutPayment.objects.create(
            tenant=request.tenant, batch=original.batch, payslip=original.payslip, employee=emp,
            net_amount=original.net_amount,
            bank_name_snapshot=emp.bank_name,
            bank_account_last4_snapshot=emp.masked_bank_account(),
            bank_routing_snapshot=emp.masked_bank_routing(),
            payment_method=original.payment_method, status="pending", retry_of=original)
        _recompute_batch_status(original.batch)
    write_audit_log(request.user, original, "update", {"action": "retry"})
    messages.success(request, "Retry payment created (pending). Mark it paid once the bank confirms.")
    return redirect("hrm:payoutbatch_detail", pk=original.batch_id)
