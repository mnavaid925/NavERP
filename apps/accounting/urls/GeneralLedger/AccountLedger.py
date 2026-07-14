"""Accounting 2.2 General Ledger — AccountLedger URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("reports/ledger/<int:account_pk>/", views.gl_account_ledger, name="gl_account_ledger"),
]
