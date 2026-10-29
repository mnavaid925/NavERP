from django.urls import path

from apps.ecommerce.views.CartCheckout import ShippingMethods as views

urlpatterns = [
    path("cart-checkout/shipping-methods/", views.shippingmethodconfig_list, name="shippingmethodconfig_list"),
    path("cart-checkout/shipping-methods/create/", views.shippingmethodconfig_create, name="shippingmethodconfig_create"),
    path("cart-checkout/shipping-methods/<int:pk>/", views.shippingmethodconfig_detail, name="shippingmethodconfig_detail"),
    path("cart-checkout/shipping-methods/<int:pk>/edit/", views.shippingmethodconfig_edit, name="shippingmethodconfig_edit"),
    path("cart-checkout/shipping-methods/<int:pk>/delete/", views.shippingmethodconfig_delete, name="shippingmethodconfig_delete"),
    path("cart-checkout/shipping-methods/<int:pk>/toggle/", views.shippingmethodconfig_toggle, name="shippingmethodconfig_toggle"),
]
