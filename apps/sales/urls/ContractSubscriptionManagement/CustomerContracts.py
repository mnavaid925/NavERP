"""Sales 8.15 — CustomerContract URL patterns."""
from django.urls import path

from apps.sales.views.ContractSubscriptionManagement import CustomerContracts as views

urlpatterns = [
    path("contracts/", views.customer_contract_list, name="customer_contract_list"),
    path("contracts/create/", views.customer_contract_create, name="customer_contract_create"),
    path("contracts/<int:pk>/", views.customer_contract_detail, name="customer_contract_detail"),
    path("contracts/<int:pk>/edit/", views.customer_contract_edit, name="customer_contract_edit"),
    path("contracts/<int:pk>/delete/", views.customer_contract_delete, name="customer_contract_delete"),
    path("contracts/<int:pk>/activate/", views.customer_contract_activate, name="customer_contract_activate"),
    path("contracts/<int:pk>/generate-renewal-quote/", views.customer_contract_generate_renewal_quote, name="customer_contract_generate_renewal_quote"),
    path("contracts/<int:pk>/execute-auto-renew/", views.customer_contract_execute_auto_renew, name="customer_contract_execute_auto_renew"),
]
