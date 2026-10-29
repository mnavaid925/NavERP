from django.urls import path

from apps.ecommerce.views.InventoryStock import FulfillmentCenters as views

urlpatterns = [
    path("inventory/centers/", views.fulfillmentcenter_list, name="fulfillmentcenter_list"),
    path("inventory/centers/create/", views.fulfillmentcenter_create, name="fulfillmentcenter_create"),
    path("inventory/centers/<int:pk>/", views.fulfillmentcenter_detail, name="fulfillmentcenter_detail"),
    path("inventory/centers/<int:pk>/edit/", views.fulfillmentcenter_edit, name="fulfillmentcenter_edit"),
    path("inventory/centers/<int:pk>/delete/", views.fulfillmentcenter_delete, name="fulfillmentcenter_delete"),
]
