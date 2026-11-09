from django.urls import path

from apps.assets.views.AssetPerformance import AssetDowntimeLogs as views

urlpatterns = [
    path("downtime/", views.asset_downtime_log_list, name="asset_downtime_log_list"),
    path("downtime/create/", views.asset_downtime_log_create, name="asset_downtime_log_create"),
    path("downtime/<int:pk>/", views.asset_downtime_log_detail, name="asset_downtime_log_detail"),
    path("downtime/<int:pk>/edit/", views.asset_downtime_log_edit, name="asset_downtime_log_edit"),
    path("downtime/<int:pk>/delete/", views.asset_downtime_log_delete, name="asset_downtime_log_delete"),
    path("downtime/<int:pk>/resolve/", views.asset_downtime_log_resolve, name="asset_downtime_log_resolve"),
]
