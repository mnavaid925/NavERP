from django.urls import path

from apps.ecommerce.views.CustomerProfile import CustomerAccountProfiles as views

urlpatterns = [
    path(
        "customer-profiles/",
        views.customeraccountprofile_list,
        name="customeraccountprofile_list",
    ),
    path(
        "customer-profiles/create/",
        views.customeraccountprofile_create,
        name="customeraccountprofile_create",
    ),
    path(
        "customer-profiles/<int:pk>/",
        views.customeraccountprofile_detail,
        name="customeraccountprofile_detail",
    ),
    path(
        "customer-profiles/<int:pk>/edit/",
        views.customeraccountprofile_edit,
        name="customeraccountprofile_edit",
    ),
    path(
        "customer-profiles/<int:pk>/delete/",
        views.customeraccountprofile_delete,
        name="customeraccountprofile_delete",
    ),
]
