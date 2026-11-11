from django.urls import path

from apps.assets.views.AssetAnalytics import PortfolioDashboards as views

urlpatterns = [
    path(
        "analytics/dashboard/",
        views.portfolio_dashboard,
        name="portfolio_dashboard",
    ),
    path(
        "analytics/dashboard/export-csv/",
        views.portfolio_dashboard_export_csv,
        name="portfolio_dashboard_export_csv",
    ),
    path(
        "analytics/scenarios/compare/",
        views.scenario_compare,
        name="scenario_compare",
    ),
]
