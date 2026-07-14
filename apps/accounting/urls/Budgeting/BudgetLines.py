"""Accounting 2.13 Budgeting & Planning — BudgetLines URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("budget-lines/add/", views.budget_line_create, name="budget_line_create"),
    path("budget-lines/<int:pk>/edit/", views.budget_line_edit, name="budget_line_edit"),
    path("budget-lines/<int:pk>/delete/", views.budget_line_delete, name="budget_line_delete"),
]
