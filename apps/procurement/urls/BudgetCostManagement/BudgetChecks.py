"""Procurement 6.15 Budget & Cost Management — Budget Availability Check URL pattern.

One GET route, ``budget-availability/`` — an advisory checker, not a record, so there is no
``add/``/``<int:pk>/`` family. The segment is collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("budget-availability/", views.budget_availability, name="budget_availability"),
]
