"""Inventory 5.17 — **Inventory Valuation Report** bullet.

Per item×LOCATION stock value under each item's own costing method — the
drill-down companion to SCM 4.3's per-item ``scm:valuation_report`` (which this
page deliberately does not duplicate or replace: its grand total is page
furniture, the accounting-grade figure stays SCM's). Every number is computed at
request time from the append-only ledger; nothing is stored.

Imports reach into ``_engine`` directly (the sub-module ``__init__`` imports
this module — routing through it would be circular).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.crud import paginate
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.views.ReportingAnalytics._engine import Ledger, q2, valuation_rows


@login_required
def report_valuation(request):
    tenant = request.tenant
    ledger = Ledger(tenant)
    rows, totals = valuation_rows(tenant, ledger=ledger)

    # Dropdown sources come from the FULL row set (StockLevels rule): a filter
    # narrows the table, never its own pickers.
    all_items = sorted({r["item"] for r in rows}, key=lambda obj: obj.sku)
    all_locations = sorted({r["location"] for r in rows if r["location"] is not None},
                           key=lambda obj: obj.code)

    # --- filters BEFORE pagination (dict rows — repo rule) ---------------------
    q = request.GET.get("q", "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["item"].sku.lower() or q in r["item"].name.lower()]
    item_filter = request.GET.get("item", "").strip()
    if item_filter.isdecimal():
        rows = [r for r in rows if str(r["item"].pk) == item_filter]
    location_filter = request.GET.get("location", "").strip()
    if location_filter.isdecimal():
        rows = [r for r in rows if r["location"] is not None
                and str(r["location"].pk) == location_filter]
    method = request.GET.get("method", "").strip()
    if method:
        rows = [r for r in rows if r["item"].costing_method == method]

    page_obj = paginate(request, rows, per_page=25)
    return render(request, "inventory/reports/valuation.html", {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "spots": totals["spots"],
        "q": request.GET.get("q", ""),
        "items": all_items,
        "locations": all_locations,
        "method": method,
        "method_choices": [("weighted_avg", "Weighted Avg"), ("fifo", "FIFO"), ("lifo", "LIFO")],
        # The grand total stays FULL-SET on purpose: filtering narrows the table,
        # not the warehouse truth a month-end reader needs.
        "grand_total": q2(totals["total_value"]),
    })
