from django.urls import path

from apps.bi.views.IntegrationHub import WarehouseSyncEndpoints as views

urlpatterns = [
    path("warehouse-syncs/", views.warehouse_sync_endpoint_list, name="warehouse_sync_endpoint_list"),
    path("warehouse-syncs/create/", views.warehouse_sync_endpoint_create, name="warehouse_sync_endpoint_create"),
    path("warehouse-syncs/<int:pk>/", views.warehouse_sync_endpoint_detail, name="warehouse_sync_endpoint_detail"),
    path("warehouse-syncs/<int:pk>/edit/", views.warehouse_sync_endpoint_edit, name="warehouse_sync_endpoint_edit"),
    path("warehouse-syncs/<int:pk>/delete/", views.warehouse_sync_endpoint_delete, name="warehouse_sync_endpoint_delete"),
    path("warehouse-syncs/<int:pk>/trigger/", views.warehouse_sync_endpoint_trigger, name="warehouse_sync_endpoint_trigger"),
]
