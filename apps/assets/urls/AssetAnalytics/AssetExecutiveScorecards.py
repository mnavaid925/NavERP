from django.urls import path

from apps.assets.views.AssetAnalytics import AssetExecutiveScorecards as views

urlpatterns = [
    path(
        "analytics/scorecards/",
        views.asset_executive_scorecard_list,
        name="asset_executive_scorecard_list",
    ),
    path(
        "analytics/scorecards/new/",
        views.asset_executive_scorecard_create,
        name="asset_executive_scorecard_create",
    ),
    path(
        "analytics/scorecards/export-csv/",
        views.asset_executive_scorecard_export_csv,
        name="asset_executive_scorecard_export_csv",
    ),
    path(
        "analytics/scorecards/<int:pk>/",
        views.asset_executive_scorecard_detail,
        name="asset_executive_scorecard_detail",
    ),
    path(
        "analytics/scorecards/<int:pk>/edit/",
        views.asset_executive_scorecard_edit,
        name="asset_executive_scorecard_edit",
    ),
    path(
        "analytics/scorecards/<int:pk>/delete/",
        views.asset_executive_scorecard_delete,
        name="asset_executive_scorecard_delete",
    ),
    path(
        "analytics/scorecards/<int:pk>/compute/",
        views.asset_executive_scorecard_compute,
        name="asset_executive_scorecard_compute",
    ),
    path(
        "analytics/scorecards/<int:pk>/publish/",
        views.asset_executive_scorecard_publish,
        name="asset_executive_scorecard_publish",
    ),
    path(
        "analytics/scorecards/<int:pk>/approve/",
        views.asset_executive_scorecard_approve,
        name="asset_executive_scorecard_approve",
    ),
    path(
        "analytics/scorecards/<int:pk>/archive/",
        views.asset_executive_scorecard_archive,
        name="asset_executive_scorecard_archive",
    ),
]
