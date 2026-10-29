from django.urls import path

from apps.ecommerce.views.OrderManagement import EcommerceOrders as views

urlpatterns = [
    path("orders/", views.ecommerceorder_list, name="ecommerceorder_list"),
    path("orders/create/", views.ecommerceorder_create, name="ecommerceorder_create"),
    path("orders/<int:pk>/", views.ecommerceorder_detail, name="ecommerceorder_detail"),
    path("orders/<int:pk>/edit/", views.ecommerceorder_edit, name="ecommerceorder_edit"),
    path("orders/<int:pk>/delete/", views.ecommerceorder_delete, name="ecommerceorder_delete"),
    path("orders/<int:pk>/cancel/", views.ecommerceorder_cancel, name="ecommerceorder_cancel"),
]
