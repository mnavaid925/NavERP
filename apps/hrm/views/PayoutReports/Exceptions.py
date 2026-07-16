"""HRM 3.17 Payout & Reports — Exceptions views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PayoutBatch,
    PayoutPayment,
)


@login_required
def payout_exceptions(request):
    """Failed/returned payments not yet retried, across all batches — the exception/follow-up report."""
    qs = (PayoutPayment.objects.filter(
            tenant=request.tenant, status__in=["failed", "returned"], retries__isnull=True)
          .select_related("batch__cycle", "employee__party").order_by("-batch__created_at"))
    batch_id = request.GET.get("batch", "").strip()
    if batch_id.isdigit():
        qs = qs.filter(batch_id=int(batch_id))
    return render(request, "hrm/payout/exceptions.html", {
        "payments": qs, "batches": PayoutBatch.objects.filter(tenant=request.tenant)})
