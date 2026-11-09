from django.urls import path

from apps.assets.views.AssetMaintenance import AssetMaintenanceLogs as views

urlpatterns = [
    path("logs/", views.asset_maintenance_log_list, name="asset_maintenance_log_list"),
    path("logs/create/", views.asset_maintenance_log_create, name="asset_maintenance_log_create"),
    path("logs/<int:pk>/", views.asset_maintenance_log_detail, name="asset_maintenance_log_detail"),
    path("logs/<int:pk>/edit/", views.asset_maintenance_log_edit, name="asset_maintenance_log_edit"),
    path("logs/<int:pk>/delete/", views.asset_maintenance_log_delete, name="asset_maintenance_log_delete"),
    path("logs/<int:pk>/submit-review/", views.asset_maintenance_log_submit_review, name="asset_maintenance_log_submit_review"),
    path("logs/<int:pk>/approve/", views.asset_maintenance_log_approve, name="asset_maintenance_log_approve"),
    path("logs/<int:pk>/post-gl/", views.asset_maintenance_log_post_gl, name="asset_maintenance_log_post_gl"),
]
