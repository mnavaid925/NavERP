"""Accounting 2.2 General Ledger — ExchangeRates URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("exchange-rates/", views.exchange_rate_list, name="exchange_rate_list"),
    path("exchange-rates/add/", views.exchange_rate_create, name="exchange_rate_create"),
    path("exchange-rates/<int:pk>/", views.exchange_rate_detail, name="exchange_rate_detail"),
    path("exchange-rates/<int:pk>/edit/", views.exchange_rate_edit, name="exchange_rate_edit"),
    path("exchange-rates/<int:pk>/delete/", views.exchange_rate_delete, name="exchange_rate_delete"),
]
