"""Inventory 5.17 — **Stock Turnover Ratio** bullet.

Per-item turnover over a selectable trailing window: how quickly stock is sold
and replaced. turns = COGS (customer-issue cost in the window) ÷ average
inventory VALUE under the item's own costing method; days_on_hand reads "how
long would today's stock last at this rate" and answers None — never a fake
zero — when the window had no demand or no stock to turn. The single-number
KPI twin is SCM 4.11's ``inv_turnover`` tile; this page shows the items.

Imports reach into ``_engine`` directly (the sub-module ``__init__`` imports
this module — routing through it would be circular).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.crud import paginate
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.views.ReportingAnalytics._engine import (
    WINDOW_CHOICES, Ledger, VELOCITY_CHOICES, clamp_window, q2, turnover_rows,
)


@login_required
def report_turnover(request):
    tenant = request.tenant
    days = clamp_window(request.GET.get("days"))
    ledger = Ledger(tenant)
    rows, totals = turnover_rows(tenant, days, ledger=ledger)

    all_items = sorted({r["item"] for r in rows}, key=lambda obj: obj.sku)

    q = request.GET.get("q", "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["item"].sku.lower() or q in r["item"].name.lower()]
    velocity = request.GET.get("velocity", "").strip()
    if velocity:
        rows = [r for r in rows if r["velocity"] == velocity]

    page_obj = paginate(request, rows, per_page=25)
    return render(request, "inventory/reports/turnover.html", {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "days": days,
        "window_choices": WINDOW_CHOICES,
        "q": request.GET.get("q", ""),
        "items": all_items,
        "velocity": velocity,
        "velocity_choices": VELOCITY_CHOICES,
        "totals": {"total_cogs": q2(totals["total_cogs"]),
                   "window_days": totals["window_days"], "items": totals["items"]},
    })
