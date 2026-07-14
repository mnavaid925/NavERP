"""Accounting 2.2 General Ledger — Currencies URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.2 GL — Currencies & exchange rates
    path("currencies/", views.currency_list, name="currency_list"),
    path("currencies/add/", views.currency_create, name="currency_create"),
    path("currencies/<int:pk>/", views.currency_detail, name="currency_detail"),
    path("currencies/<int:pk>/edit/", views.currency_edit, name="currency_edit"),
    path("currencies/<int:pk>/delete/", views.currency_delete, name="currency_delete"),
]
