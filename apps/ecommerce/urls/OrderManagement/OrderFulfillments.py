from django.urls import path

from apps.ecommerce.views.OrderManagement import OrderFulfillments as views

urlpatterns = [
    path("fulfillments/", views.orderfulfillment_list, name="orderfulfillment_list"),
    path("fulfillments/create/", views.orderfulfillment_create, name="orderfulfillment_create"),
    path("fulfillments/<int:pk>/", views.orderfulfillment_detail, name="orderfulfillment_detail"),
    path("fulfillments/<int:pk>/edit/", views.orderfulfillment_edit, name="orderfulfillment_edit"),
    path("fulfillments/<int:pk>/delete/", views.orderfulfillment_delete, name="orderfulfillment_delete"),
    path("fulfillments/<int:pk>/ship/", views.orderfulfillment_ship, name="orderfulfillment_ship"),
]
