from django.urls import path

from apps.assets.views.AssetAnalytics import AssetReplacementPlans as views

urlpatterns = [
    path(
        "analytics/replacement-plans/",
        views.asset_replacement_plan_list,
        name="asset_replacement_plan_list",
    ),
    path(
        "analytics/replacement-plans/new/",
        views.asset_replacement_plan_create,
        name="asset_replacement_plan_create",
    ),
    path(
        "analytics/replacement-plans/export-csv/",
        views.asset_replacement_plan_export_csv,
        name="asset_replacement_plan_export_csv",
    ),
    path(
        "analytics/replacement-plans/<int:pk>/",
        views.asset_replacement_plan_detail,
        name="asset_replacement_plan_detail",
    ),
    path(
        "analytics/replacement-plans/<int:pk>/edit/",
        views.asset_replacement_plan_edit,
        name="asset_replacement_plan_edit",
    ),
    path(
        "analytics/replacement-plans/<int:pk>/delete/",
        views.asset_replacement_plan_delete,
        name="asset_replacement_plan_delete",
    ),
    path(
        "analytics/replacement-plans/<int:pk>/recalculate/",
        views.asset_replacement_plan_recalculate,
        name="asset_replacement_plan_recalculate",
    ),
    path(
        "analytics/replacement-plans/<int:pk>/status/",
        views.asset_replacement_plan_transition,
        name="asset_replacement_plan_transition",
    ),
]
