"""Accounting 2.13 Budgeting & Planning — Budgets URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.13 Budgeting & planning
    path("budgets/", views.budget_list, name="budget_list"),
    path("budgets/add/", views.budget_create, name="budget_create"),
    path("budgets/<int:pk>/", views.budget_detail, name="budget_detail"),
    path("budgets/<int:pk>/edit/", views.budget_edit, name="budget_edit"),
]
