"""Procurement 6.15 Budget & Cost Management — Budget Variance Report URL patterns.

One first segment, ``budget-variance/``, with a literal ``export/`` child for the CSV download.
Django is first-match-wins, so ``export/`` is declared in reading order before anything that
could take an ``<int:pk>`` — which this segment has none of, the report being computed over
whatever budget / fiscal period the query string selects.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("budget-variance/", views.budget_variance, name="budget_variance"),
    path("budget-variance/export/", views.budget_variance_export, name="budget_variance_export"),
]
