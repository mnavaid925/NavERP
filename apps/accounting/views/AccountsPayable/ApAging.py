"""Accounting 2.3 Accounts Payable — ApAging views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _aging
from apps.accounting.models import (
    Bill,
)


@login_required
def ap_aging(request):
    tenant = request.tenant
    party_rows, totals = [], {}
    if tenant is not None:
        docs = list(Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES)
                    .select_related("party")
                    .annotate(paid_agg=Sum("allocations__allocated_amount",
                                           filter=Q(allocations__payment__status="confirmed"))))
        party_rows, totals = _aging(docs, "due_date", timezone.localdate())
    return render(request, "accounting/payable/ap_aging.html", {"party_rows": party_rows, "totals": totals})
