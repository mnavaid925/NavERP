"""Sales 8.15 — RenewalAutomations URL patterns."""
from django.urls import path

from apps.sales.views.ContractSubscriptionManagement import RenewalAutomations as views

urlpatterns = [
    path("renewal-automation-dashboard/", views.renewal_automation_dashboard, name="renewal_automation_dashboard"),
]
