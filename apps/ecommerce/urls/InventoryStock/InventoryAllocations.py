from django.urls import path

from apps.ecommerce.views.InventoryStock import InventoryAllocations as views

urlpatterns = [
    path("inventory/allocations/", views.inventoryallocation_list, name="inventoryallocation_list"),
    path("inventory/allocations/create/", views.inventoryallocation_create, name="inventoryallocation_create"),
    path("inventory/allocations/<int:pk>/", views.inventoryallocation_detail, name="inventoryallocation_detail"),
    path("inventory/allocations/<int:pk>/edit/", views.inventoryallocation_edit, name="inventoryallocation_edit"),
    path("inventory/allocations/<int:pk>/adjust/", views.inventoryallocation_adjust, name="inventoryallocation_adjust"),
    path("inventory/allocations/<int:pk>/delete/", views.inventoryallocation_delete, name="inventoryallocation_delete"),
]
