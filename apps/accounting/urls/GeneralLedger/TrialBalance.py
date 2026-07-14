"""Accounting 2.2 General Ledger — TrialBalance URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("reports/trial-balance/", views.trial_balance, name="trial_balance"),
]
