"""HRM 3.17 Payout & Reports — PaymentRegister views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PayoutBatch,
    PayoutPayment,
)


# ---------------------------------------------------------- Reports (no new model)
@login_required
def payment_register(request, pk):
    """Bank-advice / payment-register report over one batch's current payments — by status, by method,
    plus the per-employee advice rows (masked accounts, amount, UTR)."""
    batch = get_object_or_404(PayoutBatch.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    cur = batch._current_payments()
    payments = cur.select_related("employee__party").order_by("employee__party__name")
    by_status = list(cur.values("status").annotate(c=Count("id"), a=Sum("net_amount")).order_by("status"))
    by_method = list(cur.values("payment_method").annotate(c=Count("id"), a=Sum("net_amount"))
                     .order_by("payment_method"))
    # Attach human labels (the group-by loses get_*_display).
    status_labels = dict(PayoutPayment.STATUS_CHOICES)
    method_labels = dict(PayoutPayment.PAYMENT_METHOD_CHOICES)
    for r in by_status:
        r["label"] = status_labels.get(r["status"], r["status"])
    for r in by_method:
        r["label"] = method_labels.get(r["payment_method"], r["payment_method"])
    return render(request, "hrm/payout/payment_register.html", {
        "batch": batch, "payments": payments, "by_status": by_status, "by_method": by_method})
