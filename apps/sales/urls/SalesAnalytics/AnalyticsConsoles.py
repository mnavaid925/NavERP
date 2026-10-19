"""Sales 8.12 — URLs for the six derived Sales Analytics & Intelligence consoles.

The console routes are **literal** segments under the ``sales-analytics/`` prefix, so no
console path can ever be swallowed by an entity's ``<int:pk>`` route. They are spliced into
``apps/sales/urls/SalesAnalytics/__init__.py`` FIRST, ahead of the four entity modules.
"""
from django.urls import path

from apps.sales.views.SalesAnalytics import AnalyticsConsoles as views

urlpatterns = [
    path("sales-analytics/", views.analytics_console, name="analytics_console"),
    path("sales-analytics/win-loss/", views.win_loss_console, name="win_loss_console"),
    path("sales-analytics/velocity/", views.velocity_console, name="velocity_console"),
    path("sales-analytics/funnel/", views.funnel_console, name="funnel_console"),
    path(
        "sales-analytics/rep-scorecards/",
        views.rep_scorecard_console,
        name="rep_scorecard_console",
    ),
    path("sales-analytics/benchmarks/", views.benchmark_console, name="benchmark_console"),
]
