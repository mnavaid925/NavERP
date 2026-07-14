"""Accounting 2.12 Reporting & Compliance — BalanceSheet URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.12 Reporting & compliance
    path("reports/balance-sheet/", views.balance_sheet, name="balance_sheet"),
]
