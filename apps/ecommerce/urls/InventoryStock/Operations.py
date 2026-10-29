from django.urls import path

from apps.ecommerce.views.InventoryStock import Operations as views

urlpatterns = [
    path("inventory/", views.inventory_operations, name="inventory_operations"),
]
