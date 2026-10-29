from django.urls import path

from apps.ecommerce.views.CartCheckout import Carts as views

urlpatterns = [
    path("cart-checkout/carts/", views.cart_list, name="cart_list"),
    path("cart-checkout/carts/create/", views.cart_create, name="cart_create"),
    path("cart-checkout/carts/<int:pk>/", views.cart_detail, name="cart_detail"),
    path("cart-checkout/carts/<int:pk>/edit/", views.cart_edit, name="cart_edit"),
    path("cart-checkout/carts/<int:pk>/delete/", views.cart_delete, name="cart_delete"),
    path("cart-checkout/carts/<int:pk>/recover/", views.cart_recover, name="cart_recover"),
]
