"""Sales 8.15 — ContractObligation URL patterns."""
from django.urls import path

from apps.sales.views.ContractSubscriptionManagement import ContractObligations as views

urlpatterns = [
    path("obligations/", views.contract_obligation_list, name="contract_obligation_list"),
    path("obligations/create/", views.contract_obligation_create, name="contract_obligation_create"),
    path("obligations/<int:pk>/", views.contract_obligation_detail, name="contract_obligation_detail"),
    path("obligations/<int:pk>/edit/", views.contract_obligation_edit, name="contract_obligation_edit"),
    path("obligations/<int:pk>/delete/", views.contract_obligation_delete, name="contract_obligation_delete"),
    path("obligations/<int:pk>/fulfill/", views.contract_obligation_fulfill, name="contract_obligation_fulfill"),
    path("obligations/<int:pk>/breach/", views.contract_obligation_breach, name="contract_obligation_breach"),
]
