from django.urls import path

from apps.bi.views.DataWarehouse import WarehouseTables as views

urlpatterns = [
    path("warehouse-tables/", views.warehouse_table_list, name="warehouse_table_list"),
    path("warehouse-tables/create/", views.warehouse_table_create, name="warehouse_table_create"),
    path("warehouse-tables/<int:pk>/", views.warehouse_table_detail, name="warehouse_table_detail"),
    path("warehouse-tables/<int:pk>/edit/", views.warehouse_table_edit, name="warehouse_table_edit"),
    path("warehouse-tables/<int:pk>/delete/", views.warehouse_table_delete, name="warehouse_table_delete"),
    path("warehouse-tables/<int:pk>/ddl/", views.warehouse_table_ddl_preview, name="warehouse_table_ddl_preview"),
    path("warehouse-tables/<int:pk>/analyze/", views.warehouse_table_analyze, name="warehouse_table_analyze"),
]
