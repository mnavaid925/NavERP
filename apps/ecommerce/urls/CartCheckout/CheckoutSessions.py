from django.urls import path

from apps.ecommerce.views.CartCheckout import CheckoutSessions as views

urlpatterns = [
    path("cart-checkout/sessions/", views.checkoutsession_list, name="checkoutsession_list"),
    path("cart-checkout/sessions/create/", views.checkoutsession_create, name="checkoutsession_create"),
    path("cart-checkout/sessions/<int:pk>/", views.checkoutsession_detail, name="checkoutsession_detail"),
    path("cart-checkout/sessions/<int:pk>/edit/", views.checkoutsession_edit, name="checkoutsession_edit"),
    path("cart-checkout/sessions/<int:pk>/delete/", views.checkoutsession_delete, name="checkoutsession_delete"),
    path("cart-checkout/sessions/<int:pk>/advance/", views.checkoutsession_advance, name="checkoutsession_advance"),
]
