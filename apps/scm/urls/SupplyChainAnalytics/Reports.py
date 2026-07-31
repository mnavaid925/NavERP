"""SCM 4.11 Supply Chain Analytics — the five computed report pages and their CSV exports.

COLLISION CHECK — five first segments, each checked against the WHOLE concatenated urlconf rather
than merely against this block:

  inventory-analytics/  ) nothing existing starts with ``inventory``, ``spend``, ``logistics`` or
  spend-analytics/      ) ``margin``. 4.3's inventory pages sit on ``valuation/``, ``on-hand/``,
  logistics-kpis/       ) ``stock-ledger/`` and ``reorder-alerts/``, none of which is a prefix of
  margin-analytics/     ) these. FREE.
  disruption-risk/      — 4.2 owns ``risk-assessments/``; ``disruption-risk`` is a distinct whole
                          first component, so neither can shadow the other. FREE.

Each CSV export is a LITERAL ``export/`` sub-route under an already-claimed segment, so the five
exports add zero new first segments and zero new collision surface. This module declares NO pk route
at all and NO greedy ``<str:…>`` converter — 4.10's ``return-tracking/<str:token>/`` remains the
app's only one — so nothing here can shadow or be shadowed by a later ``<int:pk>/`` route.

These five ARE the five NavERP 4.11 sidebar bullets, and they are five DISTINCT destinations (L30 —
the "four bullets, one URL" failure). Every page is computed live over 4.1-4.10 (the 4.3
``valuation_report`` precedent) and is read-only: nothing in this module writes a ``StockMove``, a
``JournalEntry`` or any 4.1-4.10 row.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # 4.11 bullet 1 — Inventory Dashboards.
    path("inventory-analytics/", views.inventory_analytics, name="inventory_analytics"),
    path("inventory-analytics/export/", views.inventory_analytics_export,
         name="inventory_analytics_export"),
    # 4.11 bullet 2 — Procurement Analytics (spend cube + savings).
    path("spend-analytics/", views.spend_analytics, name="spend_analytics"),
    path("spend-analytics/export/", views.spend_analytics_export, name="spend_analytics_export"),
    # 4.11 bullet 3 — Logistics KPIs (carrier / lane / utilization scorecards).
    path("logistics-kpis/", views.logistics_kpis, name="logistics_kpis"),
    path("logistics-kpis/export/", views.logistics_kpis_export, name="logistics_kpis_export"),
    # 4.11 bullet 4 — Financial Reporting: OPERATIONAL margin and cost-to-serve, not the statutory
    # ledger (L29 — accounting owns that spine; 4.11 never posts to it).
    path("margin-analytics/", views.margin_analytics, name="margin_analytics"),
    path("margin-analytics/export/", views.margin_analytics_export, name="margin_analytics_export"),
    # 4.11 bullet 5 — Predictive Analytics: explainable deterministic composites, not ML (10.13).
    path("disruption-risk/", views.disruption_risk, name="disruption_risk"),
    path("disruption-risk/export/", views.disruption_risk_export, name="disruption_risk_export"),
]
