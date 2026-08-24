"""Inventory 5.17 — **ABC Analysis** bullet.

Pareto classification of the stocked item master by consumption VALUE over a
trailing window (A = top 80% of issued cost, B = next 15%, C = tail), overlaid
with the turnover engine's velocity verdict so an A-class but dead-slow SKU is
visible as exactly that. This is a live READ over the ledger; it deliberately
does NOT write ``scm.ReorderRule.abc_class`` — 4.7's stored class is planning
configuration owned there, this page is analysis owned here.

Imports reach into ``_engine`` directly (the sub-module ``__init__`` imports
this module — routing through it would be circular).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.crud import paginate
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.views.ReportingAnalytics._engine import (
    WINDOW_CHOICES, Ledger, VELOCITY_CHOICES, abc_rows, clamp_window, f2,
)


@login_required
def report_abc(request):
    tenant = request.tenant
    days = clamp_window(request.GET.get("days"))
    ledger = Ledger(tenant)
    rows, stats = abc_rows(tenant, days, ledger=ledger)

    all_items = sorted({r["item"] for r in rows}, key=lambda obj: obj.sku)

    q = request.GET.get("q", "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["item"].sku.lower() or q in r["item"].name.lower()]
    abc_class = request.GET.get("class", "").strip().upper()
    if abc_class:
        rows = [r for r in rows if r["abc_class"] == abc_class]
    velocity = request.GET.get("velocity", "").strip()
    if velocity:
        rows = [r for r in rows if r["velocity"] == velocity]

    page_obj = paginate(request, rows, per_page=25)
    return render(request, "inventory/reports/abc.html", {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "days": days,
        "window_choices": WINDOW_CHOICES,
        "q": request.GET.get("q", ""),
        "items": all_items,
        "abc_class": abc_class,
        "velocity": velocity,
        "velocity_choices": VELOCITY_CHOICES,
        "stats": {k: (f2(v) if k == "a_share_pct" else v) for k, v in stats.items()},
    })
