"""Accounting 2.5 Cash Management — CashForecast URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("reports/cash-forecast/", views.cash_forecast, name="cash_forecast"),
]
