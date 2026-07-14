"""Accounting 2.11 Tax — TaxReturns URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("tax-returns/", views.tax_return_list, name="tax_return_list"),
    path("tax-returns/add/", views.tax_return_create, name="tax_return_create"),
    path("tax-returns/<int:pk>/", views.tax_return_detail, name="tax_return_detail"),
    path("tax-returns/<int:pk>/edit/", views.tax_return_edit, name="tax_return_edit"),
    path("tax-returns/<int:pk>/delete/", views.tax_return_delete, name="tax_return_delete"),
]
