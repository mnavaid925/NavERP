from django.urls import path

from apps.bi.views.IntegrationHub import WarehouseSyncEndpoints as views

urlpatterns = [
    path("integrations/warehouse-syncs/", views.warehouse_sync_endpoint_list, name="warehouse_sync_endpoint_list"),
    path("integrations/warehouse-syncs/create/", views.warehouse_sync_endpoint_create, name="warehouse_sync_endpoint_create"),
    path("integrations/warehouse-syncs/<int:pk>/", views.warehouse_sync_endpoint_detail, name="warehouse_sync_endpoint_detail"),
    path("integrations/warehouse-syncs/<int:pk>/edit/", views.warehouse_sync_endpoint_edit, name="warehouse_sync_endpoint_edit"),
    path("integrations/warehouse-syncs/<int:pk>/delete/", views.warehouse_sync_endpoint_delete, name="warehouse_sync_endpoint_delete"),
    path("integrations/warehouse-syncs/<int:pk>/trigger/", views.warehouse_sync_endpoint_trigger, name="warehouse_sync_endpoint_trigger"),
]
