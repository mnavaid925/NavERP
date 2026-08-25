"""Procurement 6.8 Contract Management — ContractAmendment urlconf."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal segments first — Django is first-match-wins.
    path("contract-amendments/", views.camendment_list, name="camendment_list"),
    path("contract-amendments/add/", views.camendment_create, name="camendment_create"),
    path("contract-amendments/<int:pk>/", views.camendment_detail,
         name="camendment_detail"),
    path("contract-amendments/<int:pk>/approve/", views.camendment_approve,
         name="camendment_approve"),
    path("contract-amendments/<int:pk>/reject/", views.camendment_reject,
         name="camendment_reject"),
]
