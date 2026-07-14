"""Accounting 2.2 General Ledger — GLAccounts URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.2 GL — Chart of Accounts
    path("glaccounts/", views.glaccount_list, name="glaccount_list"),
    path("glaccounts/add/", views.glaccount_create, name="glaccount_create"),
    path("glaccounts/<int:pk>/", views.glaccount_detail, name="glaccount_detail"),
    path("glaccounts/<int:pk>/edit/", views.glaccount_edit, name="glaccount_edit"),
    path("glaccounts/<int:pk>/delete/", views.glaccount_delete, name="glaccount_delete"),
]
