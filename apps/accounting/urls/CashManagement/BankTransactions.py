"""Accounting 2.5 Cash Management — BankTransactions URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.5 Cash — Bank transactions
    path("bank-transactions/", views.bank_transaction_list, name="bank_transaction_list"),
    path("bank-transactions/add/", views.bank_transaction_create, name="bank_transaction_create"),
    path("bank-transactions/import-csv/", views.bank_transaction_import_csv, name="bank_transaction_import_csv"),
    path("bank-transactions/<int:pk>/", views.bank_transaction_detail, name="bank_transaction_detail"),
    path("bank-transactions/<int:pk>/edit/", views.bank_transaction_edit, name="bank_transaction_edit"),
    path("bank-transactions/<int:pk>/delete/", views.bank_transaction_delete, name="bank_transaction_delete"),
]
