"""Sales 8.15 — ContractSubscriptionWorkspace URL patterns."""
from django.urls import path

from apps.sales.views.ContractSubscriptionManagement import ContractSubscriptionWorkspaces as views

urlpatterns = [
    path("contract-subscription-workspace/", views.contract_subscription_workspace, name="contract_subscription_workspace"),
]
