"""Accounting 2.13 Budgeting & Planning — BudgetVariance URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("budgets/<int:pk>/delete/", views.budget_delete, name="budget_delete"),
    path("reports/budget-variance/", views.budget_variance, name="budget_variance"),
]
