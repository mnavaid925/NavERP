from django.urls import path

from apps.ecommerce.views.CustomerProfile import CustomerAddressPreferences as views

urlpatterns = [
    path(
        "address-preferences/",
        views.customeraddresspreference_list,
        name="customeraddresspreference_list",
    ),
    path(
        "address-preferences/create/",
        views.customeraddresspreference_create,
        name="customeraddresspreference_create",
    ),
    path(
        "address-preferences/<int:pk>/",
        views.customeraddresspreference_detail,
        name="customeraddresspreference_detail",
    ),
    path(
        "address-preferences/<int:pk>/edit/",
        views.customeraddresspreference_edit,
        name="customeraddresspreference_edit",
    ),
    path(
        "address-preferences/<int:pk>/delete/",
        views.customeraddresspreference_delete,
        name="customeraddresspreference_delete",
    ),
]
