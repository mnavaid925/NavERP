"""Accounting 2.12 Reporting & Compliance — ProfitAndLoss URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("reports/profit-and-loss/", views.profit_and_loss, name="profit_and_loss"),
]
