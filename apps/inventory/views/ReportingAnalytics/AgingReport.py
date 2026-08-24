"""Inventory 5.17 — **Aging Analysis** bullet.

Per item×LOCATION FIFO age buckets over the PHYSICAL layers of the ledger:
how long has today's stock actually been sitting here, and which of it is slow
or dead. Health comes from the last outbound draw of any kind (issue,
consumption, maintenance): no draw for 61–90 days reads slow, 91+ reads dead.
The single-number dead-stock KPI twin is SCM 4.11's ``inv_dead_stock_value``;
this page shows the spots behind it. Expiry risk on dated stock stays with the
5.8 FEFO board, which owns that verdict.

Imports reach into ``_engine`` directly rather than through the sub-module
package ``__init__`` — that __init__ imports THIS module, so routing constants
through it would be a circular import.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.crud import paginate
from apps.inventory.views.ReportingAnalytics._engine import (
    AGING_BUCKETS, BUCKET_LABELS, HEALTH_CHOICES, HEALTH_CSS, Ledger, aging_rows, q2,
)


@login_required
def report_aging(request):
    tenant = request.tenant
    ledger = Ledger(tenant)
    rows, totals = aging_rows(tenant, ledger=ledger)

    q = request.GET.get("q", "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["item"].sku.lower() or q in r["item"].name.lower()]
    location_filter = request.GET.get("location", "").strip()
    if location_filter.isdecimal():
        rows = [r for r in rows if r["location"] is not None
                and str(r["location"].pk) == location_filter]
    health = request.GET.get("health", "").strip()
    if health:
        rows = [r for r in rows if r["health"] == health]
    bucket = request.GET.get("bucket", "").strip()
    if bucket in BUCKET_LABELS:
        rows = [r for r in rows if r["buckets"][bucket]["qty"] > 0]

    items = sorted({r["item"] for r in rows}, key=lambda obj: obj.sku)
    locations = sorted({r["location"] for r in rows if r["location"] is not None},
                       key=lambda obj: obj.code)
    counts = {h: sum(1 for r in rows if r["health"] == h) for h, _label in HEALTH_CHOICES}

    page_obj = paginate(request, rows, per_page=25)
    return render(request, "inventory/reports/aging.html", {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "bucket_labels": BUCKET_LABELS,
        "bucket_defs": AGING_BUCKETS,
        "q": request.GET.get("q", ""),
        "items": items,
        "locations": locations,
        "health": health,
        "health_css": HEALTH_CSS,
        "health_choices": HEALTH_CHOICES,
        "bucket": bucket,
        "counts": counts,
        # Full-set totals regardless of filters (month-end truth, as on valuation).
        "totals": {"total_value": q2(totals["total_value"]),
                   "dead_value": q2(totals["dead_value"]),
                   "spots": totals["spots"]},
    })
