"""Accounting 2.5 Cash Management — BankAccounts URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.5 Cash — Bank accounts
    path("bank-accounts/", views.bank_account_list, name="bank_account_list"),
    path("bank-accounts/add/", views.bank_account_create, name="bank_account_create"),
    path("bank-accounts/<int:pk>/", views.bank_account_detail, name="bank_account_detail"),
    path("bank-accounts/<int:pk>/edit/", views.bank_account_edit, name="bank_account_edit"),
    path("bank-accounts/<int:pk>/delete/", views.bank_account_delete, name="bank_account_delete"),
]
