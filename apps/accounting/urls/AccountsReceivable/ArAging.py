"""Accounting 2.4 Accounts Receivable — ArAging URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("reports/ar-aging/", views.ar_aging, name="ar_aging"),
]
