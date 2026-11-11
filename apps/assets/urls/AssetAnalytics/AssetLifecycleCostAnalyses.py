from django.urls import path

from apps.assets.views.AssetAnalytics import AssetLifecycleCostAnalyses as views

urlpatterns = [
    path(
        "analytics/lifecycle-cost/",
        views.asset_lifecycle_cost_analysis_list,
        name="asset_lifecycle_cost_analysis_list",
    ),
    path(
        "analytics/lifecycle-cost/new/",
        views.asset_lifecycle_cost_analysis_create,
        name="asset_lifecycle_cost_analysis_create",
    ),
    path(
        "analytics/lifecycle-cost/export-csv/",
        views.asset_lifecycle_cost_analysis_export_csv,
        name="asset_lifecycle_cost_analysis_export_csv",
    ),
    path(
        "analytics/lifecycle-cost/<int:pk>/",
        views.asset_lifecycle_cost_analysis_detail,
        name="asset_lifecycle_cost_analysis_detail",
    ),
    path(
        "analytics/lifecycle-cost/<int:pk>/edit/",
        views.asset_lifecycle_cost_analysis_edit,
        name="asset_lifecycle_cost_analysis_edit",
    ),
    path(
        "analytics/lifecycle-cost/<int:pk>/delete/",
        views.asset_lifecycle_cost_analysis_delete,
        name="asset_lifecycle_cost_analysis_delete",
    ),
    path(
        "analytics/lifecycle-cost/<int:pk>/populate/",
        views.asset_lifecycle_cost_analysis_populate,
        name="asset_lifecycle_cost_analysis_populate",
    ),
    path(
        "analytics/lifecycle-cost/<int:pk>/status/",
        views.asset_lifecycle_cost_analysis_transition,
        name="asset_lifecycle_cost_analysis_transition",
    ),
]
