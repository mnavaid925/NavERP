"""Sales 8.11 — URLs for `CustomerRenewal`."""
from django.urls import path

from apps.sales.views.CustomerSuccess import CustomerRenewals as views

urlpatterns = [
    path("customer-success/renewals/", views.customer_renewal_list, name="customer_renewal_list"),
    path("customer-success/renewals/create/", views.customer_renewal_create, name="customer_renewal_create"),
    path("customer-success/renewals/<int:pk>/", views.customer_renewal_detail, name="customer_renewal_detail"),
    path("customer-success/renewals/<int:pk>/edit/", views.customer_renewal_edit, name="customer_renewal_edit"),
    path("customer-success/renewals/<int:pk>/delete/", views.customer_renewal_delete, name="customer_renewal_delete"),
    path("customer-success/renewal-pipeline/", views.customer_renewal_pipeline, name="customer_renewal_pipeline"),
]
