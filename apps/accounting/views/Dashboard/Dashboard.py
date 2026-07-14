"""Accounting 2.1 Dashboard & Analytics — Dashboard views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _cash_position
from apps.accounting.models import (
    BankTransaction,
    Bill,
    Invoice,
    JournalEntry,
    ZERO,
)


@login_required
def accounting_dashboard(request):
    tenant = request.tenant
    stats = {"cash_position": ZERO, "ar_outstanding": ZERO, "ap_outstanding": ZERO,
             "overdue_count": 0}
    overdue_invoices = overdue_bills = recent_je = []
    cash_labels, cash_data = [], []
    if tenant is not None:
        today = timezone.localdate()
        stats["cash_position"] = _cash_position(tenant)
        stats["ar_outstanding"] = (
            Invoice.objects.filter(tenant=tenant, status__in=Invoice.OPEN_STATUSES)
            .aggregate(s=Sum("total"))["s"] or ZERO
        )
        stats["ap_outstanding"] = (
            Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES)
            .aggregate(s=Sum("total"))["s"] or ZERO
        )
        overdue_invoices = list(
            Invoice.objects.filter(tenant=tenant, status__in=Invoice.OPEN_STATUSES,
                                   due_date__lt=today).select_related("party")[:10]
        )
        overdue_bills = list(
            Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES,
                                due_date__lt=today).select_related("party")[:10]
        )
        stats["overdue_count"] = len(overdue_invoices) + len(overdue_bills)
        recent_je = list(
            JournalEntry.objects.filter(tenant=tenant, status="posted")
            .select_related("fiscal_period").order_by("-entry_date", "-id")[:5]
        )
        # 6-week net-cash trend (Mon-anchored buckets).
        week_start = today - timedelta(days=today.weekday())
        for i in range(5, -1, -1):
            start = week_start - timedelta(weeks=i)
            end = start + timedelta(days=6)
            agg = BankTransaction.objects.filter(
                tenant=tenant, transaction_date__range=(start, end)
            ).aggregate(credit=Sum("amount", filter=Q(direction="credit")),
                        debit=Sum("amount", filter=Q(direction="debit")))
            net = (agg["credit"] or ZERO) - (agg["debit"] or ZERO)
            cash_labels.append(start.strftime("%b %d"))
            cash_data.append(float(net))
    return render(request, "accounting/dashboard.html", {
        "stats": stats,
        "overdue_invoices": overdue_invoices,
        "overdue_bills": overdue_bills,
        "recent_je": recent_je,
        "today": timezone.localdate(),
        "cash_labels": cash_labels,
        "cash_data": cash_data,
    })
