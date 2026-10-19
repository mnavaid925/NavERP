"""Sales 8.11 — URLs for `CustomerOnboarding`."""
from django.urls import path

from apps.sales.views.CustomerSuccess import CustomerOnboardings as views

urlpatterns = [
    path("customer-success/onboardings/", views.customer_onboarding_list, name="customer_onboarding_list"),
    path("customer-success/onboardings/create/", views.customer_onboarding_create, name="customer_onboarding_create"),
    path("customer-success/onboardings/<int:pk>/", views.customer_onboarding_detail, name="customer_onboarding_detail"),
    path("customer-success/onboardings/<int:pk>/edit/", views.customer_onboarding_edit, name="customer_onboarding_edit"),
    path("customer-success/onboardings/<int:pk>/delete/", views.customer_onboarding_delete, name="customer_onboarding_delete"),
    path("customer-success/onboarding-hub/", views.customer_onboarding_hub, name="customer_onboarding_hub"),
]
