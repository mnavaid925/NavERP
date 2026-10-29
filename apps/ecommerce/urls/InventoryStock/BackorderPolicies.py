from django.urls import path

from apps.ecommerce.views.InventoryStock import BackorderPolicies as views

urlpatterns = [
    path("inventory/backorders/", views.backorderpolicy_list, name="backorderpolicy_list"),
    path("inventory/backorders/create/", views.backorderpolicy_create, name="backorderpolicy_create"),
    path("inventory/backorders/<int:pk>/", views.backorderpolicy_detail, name="backorderpolicy_detail"),
    path("inventory/backorders/<int:pk>/edit/", views.backorderpolicy_edit, name="backorderpolicy_edit"),
    path("inventory/backorders/<int:pk>/delete/", views.backorderpolicy_delete, name="backorderpolicy_delete"),
]
