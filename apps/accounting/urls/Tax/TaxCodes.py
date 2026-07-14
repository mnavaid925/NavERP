"""Accounting 2.11 Tax — TaxCodes URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.11 Tax
    path("tax-codes/", views.tax_code_list, name="tax_code_list"),
    path("tax-codes/add/", views.tax_code_create, name="tax_code_create"),
    path("tax-codes/<int:pk>/", views.tax_code_detail, name="tax_code_detail"),
    path("tax-codes/<int:pk>/edit/", views.tax_code_edit, name="tax_code_edit"),
    path("tax-codes/<int:pk>/delete/", views.tax_code_delete, name="tax_code_delete"),
]
