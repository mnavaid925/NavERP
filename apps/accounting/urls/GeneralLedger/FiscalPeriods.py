"""Accounting 2.2 General Ledger — FiscalPeriods URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.2 GL — Fiscal periods
    path("fiscal-periods/", views.fiscal_period_list, name="fiscal_period_list"),
    path("fiscal-periods/add/", views.fiscal_period_create, name="fiscal_period_create"),
    path("fiscal-periods/<int:pk>/", views.fiscal_period_detail, name="fiscal_period_detail"),
    path("fiscal-periods/<int:pk>/edit/", views.fiscal_period_edit, name="fiscal_period_edit"),
    path("fiscal-periods/<int:pk>/delete/", views.fiscal_period_delete, name="fiscal_period_delete"),
    path("fiscal-periods/<int:pk>/close/", views.fiscal_period_close, name="fiscal_period_close"),
]
