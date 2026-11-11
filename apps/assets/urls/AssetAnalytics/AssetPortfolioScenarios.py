from django.urls import path

from apps.assets.views.AssetAnalytics import AssetPortfolioScenarios as views

urlpatterns = [
    path(
        "analytics/scenarios/",
        views.asset_portfolio_scenario_list,
        name="asset_portfolio_scenario_list",
    ),
    path(
        "analytics/scenarios/new/",
        views.asset_portfolio_scenario_create,
        name="asset_portfolio_scenario_create",
    ),
    path(
        "analytics/scenarios/export-csv/",
        views.asset_portfolio_scenario_export_csv,
        name="asset_portfolio_scenario_export_csv",
    ),
    path(
        "analytics/scenarios/<int:pk>/",
        views.asset_portfolio_scenario_detail,
        name="asset_portfolio_scenario_detail",
    ),
    path(
        "analytics/scenarios/<int:pk>/edit/",
        views.asset_portfolio_scenario_edit,
        name="asset_portfolio_scenario_edit",
    ),
    path(
        "analytics/scenarios/<int:pk>/delete/",
        views.asset_portfolio_scenario_delete,
        name="asset_portfolio_scenario_delete",
    ),
    path(
        "analytics/scenarios/<int:pk>/simulate/",
        views.asset_portfolio_scenario_simulate,
        name="asset_portfolio_scenario_simulate",
    ),
    path(
        "analytics/scenarios/<int:pk>/status/",
        views.asset_portfolio_scenario_transition,
        name="asset_portfolio_scenario_transition",
    ),
]
