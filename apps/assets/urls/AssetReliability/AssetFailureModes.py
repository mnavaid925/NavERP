from django.urls import path

from apps.assets.views.AssetReliability import AssetFailureModes as views

urlpatterns = [
    path("reliability/failure-modes/", views.asset_failure_mode_list, name="asset_failure_mode_list"),
    path("reliability/failure-modes/create/", views.asset_failure_mode_create, name="asset_failure_mode_create"),
    path("reliability/failure-modes/<int:pk>/", views.asset_failure_mode_detail, name="asset_failure_mode_detail"),
    path("reliability/failure-modes/<int:pk>/edit/", views.asset_failure_mode_edit, name="asset_failure_mode_edit"),
    path("reliability/failure-modes/<int:pk>/delete/", views.asset_failure_mode_delete, name="asset_failure_mode_delete"),
    path("reliability/failure-modes/<int:pk>/activate/", views.asset_failure_mode_activate, name="asset_failure_mode_activate"),
    path("reliability/failure-modes/<int:pk>/archive/", views.asset_failure_mode_archive, name="asset_failure_mode_archive"),
]
