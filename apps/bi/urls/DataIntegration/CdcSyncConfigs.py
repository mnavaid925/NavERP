from django.urls import path

from apps.bi.views.DataIntegration import CdcSyncConfigs as views

urlpatterns = [
    path("cdc/", views.cdc_sync_config_list, name="cdc_sync_config_list"),
    path("cdc/create/", views.cdc_sync_config_create, name="cdc_sync_config_create"),
    path("cdc/<int:pk>/", views.cdc_sync_config_detail, name="cdc_sync_config_detail"),
    path("cdc/<int:pk>/edit/", views.cdc_sync_config_edit, name="cdc_sync_config_edit"),
    path("cdc/<int:pk>/delete/", views.cdc_sync_config_delete, name="cdc_sync_config_delete"),
    path("cdc/<int:pk>/reset-cursor/", views.cdc_sync_config_reset_cursor, name="cdc_sync_config_reset_cursor"),
]
