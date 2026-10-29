from django.urls import path

from apps.ecommerce.views.CartCheckout import PaymentMethods as views

urlpatterns = [
    path("cart-checkout/payment-methods/", views.paymentmethodconfig_list, name="paymentmethodconfig_list"),
    path("cart-checkout/payment-methods/create/", views.paymentmethodconfig_create, name="paymentmethodconfig_create"),
    path("cart-checkout/payment-methods/<int:pk>/", views.paymentmethodconfig_detail, name="paymentmethodconfig_detail"),
    path("cart-checkout/payment-methods/<int:pk>/edit/", views.paymentmethodconfig_edit, name="paymentmethodconfig_edit"),
    path("cart-checkout/payment-methods/<int:pk>/delete/", views.paymentmethodconfig_delete, name="paymentmethodconfig_delete"),
    path("cart-checkout/payment-methods/<int:pk>/toggle/", views.paymentmethodconfig_toggle, name="paymentmethodconfig_toggle"),
]
