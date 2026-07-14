"""Accounting 2.3 Accounts Payable — ApAging URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("reports/ap-aging/", views.ap_aging, name="ap_aging"),
]
