"""Procurement 6.8 Contract Management — contract register/authoring urlconf.

``contracts/`` is this sub-module's first segment for every staff route; the PUBLIC
sign page lives under ``contract-sign/<token>/`` — a distinct literal that cannot
collide with any ``<int:pk>`` route, and deliberately OUTSIDE any login gate (the
token is the bearer credential, crm 1.9's exact posture).
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal segments first — Django is first-match-wins.
    path("contracts/", views.contract_list, name="contract_list"),
    path("contracts/add/", views.contract_create, name="contract_create"),
    path("contract-sign/<str:token>/", views.contract_sign_page,
         name="contract_sign_page"),
    path("contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:pk>/add-link/", views.contract_add_link,
         name="contract_add_link"),
    path("contracts/<int:pk>/remove-link/<int:link_id>/", views.contract_remove_link,
         name="contract_remove_link"),
    path("contracts/<int:pk>/add-signer/", views.contract_add_signer,
         name="contract_add_signer"),
    path("contracts/<int:pk>/remove-signer/<int:signer_id>/",
         views.contract_remove_signer, name="contract_remove_signer"),
]
