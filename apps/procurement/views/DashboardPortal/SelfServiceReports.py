"""Procurement 6.1 User Dashboard & Portal — Self-Service Reporting.

**Self-Service Reporting** bullet: quick personal usage and spend reports, generated at request
time over the requisition spine — my requisitions by status, what I asked for vs what got
committed this month and last, and the tenant's committed spend by month for the last six. Like
every 6.1 surface this is a COMPUTED page: it stores nothing, so a report can never disagree with
the documents it reports on.

The CSV hand-off exports the signed-in user's OWN requisitions (there is no tenant-wide export —
that is 6.14 Spend Analytics' job) with formula-injection neutralization on every cell.
"""
import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseOrder, PurchaseRequisition

#: How many months the committed-spend trend covers.
TREND_MONTHS = 6


@login_required
def report_index(request):
    me = request.user
    today = timezone.localdate()
    month_start = today.replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    trend_start = (month_start - timedelta(days=1)).replace(day=1)
    for _ in range(TREND_MONTHS - 1):
        trend_start = (trend_start - timedelta(days=1)).replace(day=1)

    mine = PurchaseRequisition.objects.filter(tenant=request.tenant, requester=me)
    by_status = dict(mine.values_list("status")
                     .annotate(n=Count("id")).values_list("status", "n"))

    committed_statuses = PurchaseRequisition.COMMITTED_STATUSES
    stats = {
        "my_total": mine.count(),
        "my_committed": _sum(mine.filter(status__in=committed_statuses)),
        "my_requested_this_month": _sum(mine.filter(created_at__gte=month_start)),
        "my_requested_last_month": _sum(mine.filter(created_at__gte=prev_month_start,
                                                    created_at__lt=month_start)),
        "tenant_committed_this_month": _sum(
            PurchaseRequisition.objects.filter(tenant=request.tenant,
                                               status__in=committed_statuses,
                                               created_at__gte=month_start)),
        "open_po_value": (PurchaseOrder.objects.filter(tenant=request.tenant)
                          .exclude(status__in=PurchaseOrder.CLOSED_STATUSES)
                          .aggregate(s=Sum("total"))["s"] or 0),
    }

    # ONE grouped query for the whole six-month trend (not an aggregate per month).
    monthly = (PurchaseRequisition.objects
               .filter(tenant=request.tenant, status__in=committed_statuses,
                       created_at__gte=trend_start)
               .annotate(month=TruncMonth("created_at"))
               .values("month")
               .annotate(total=Sum("estimated_total"), n=Count("id"))
               .order_by("month"))
    trend = [{"month": row["month"], "total": row["total"] or 0, "count": row["n"]}
             for row in monthly]

    return render(request, "procurement/dashboardportal/reports.html", {
        "stats": stats,
        "by_status": [(value, label, by_status.get(value, 0))
                      for value, label in PurchaseRequisition.STATUS_CHOICES],
        "trend": trend,
        "trend_months": TREND_MONTHS,
        "recent_of_mine": mine.order_by("-created_at", "-id")[:8],
    })


@login_required
def report_export(request):
    """My requisitions as CSV.

    # WARNING: cells start their life as user input and Excel/LibreOffice execute leading
    # '=', '+', '-' and '@' as formulas on open (CSV injection). Every cell goes through
    # _csv_safe(), which prefixes an apostrophe onto dangerous openers. Do not remove.
    """
    me = request.user
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="my-requisitions.csv"'
    writer = csv.writer(response)
    writer.writerow(["Number", "Title", "Status", "Required by", "Estimated total", "Raised on"])
    rows = (PurchaseRequisition.objects.filter(tenant=request.tenant, requester=me)
            .order_by("-created_at", "-id"))
    for req in rows:
        writer.writerow([
            _csv_safe(req.number or ""),
            _csv_safe(req.title),
            req.get_status_display(),
            req.required_by or "",
            req.estimated_total,
            timezone.localdate(req.created_at),
        ])
    return response


def _csv_safe(value):
    """Neutralize spreadsheet formula injection: prefix dangerous leading characters."""
    text = str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _sum(qs):
    return qs.aggregate(s=Sum("estimated_total"))["s"] or 0
