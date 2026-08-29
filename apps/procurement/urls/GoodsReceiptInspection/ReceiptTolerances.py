"""Procurement 6.12 Goods Receipt & Inspection — ReceiptTolerancePolicy routes."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — Django resolves first-match-wins.
    path("receipt-tolerances/", views.tolerancepolicy_list, name="tolerancepolicy_list"),
    path("receipt-tolerances/add/", views.tolerancepolicy_create, name="tolerancepolicy_create"),
    path("receipt-tolerances/<int:pk>/", views.tolerancepolicy_detail,
         name="tolerancepolicy_detail"),
    path("receipt-tolerances/<int:pk>/edit/", views.tolerancepolicy_edit,
         name="tolerancepolicy_edit"),
    path("receipt-tolerances/<int:pk>/delete/", views.tolerancepolicy_delete,
         name="tolerancepolicy_delete"),
]
