"""Accounting 2.1 Dashboard & Analytics — Dashboard URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.1 Dashboard & reports
    path("", views.accounting_dashboard, name="accounting_dashboard"),
    path("dashboard/", views.accounting_dashboard, name="dashboard"),
]
