from django.urls import path

from apps.bi.views.DataWarehouse import WarehouseStoragePolicies as views

urlpatterns = [
    path("storage-policies/", views.warehouse_storage_policy_list, name="warehouse_storage_policy_list"),
    path("storage-policies/create/", views.warehouse_storage_policy_create, name="warehouse_storage_policy_create"),
    path("storage-policies/<int:pk>/", views.warehouse_storage_policy_detail, name="warehouse_storage_policy_detail"),
    path("storage-policies/<int:pk>/edit/", views.warehouse_storage_policy_edit, name="warehouse_storage_policy_edit"),
    path("storage-policies/<int:pk>/delete/", views.warehouse_storage_policy_delete, name="warehouse_storage_policy_delete"),
]
