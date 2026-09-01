"""Procurement 6.15 Budget & Cost Management — BudgetMapping URL patterns.

One first segment, ``budget-mappings/``, collision-checked against the concatenated
``urls/__init__.py`` inventory as a whole component; the app registers no greedy ``<str:…>``
converter, so nothing can shadow it.

Django is first-match-wins, so the literal route (``add/``) is declared BEFORE the ``<int:pk>/``
one it would otherwise fall into. ``delete/`` is POST-only through the view's decorator — the
list and detail pages carry a ``{% csrf_token %}`` form with an ``onclick`` confirm instead of a
confirm template.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("budget-mappings/", views.budgetmapping_list, name="budgetmapping_list"),
    path("budget-mappings/add/", views.budgetmapping_create, name="budgetmapping_create"),
    path("budget-mappings/<int:pk>/", views.budgetmapping_detail, name="budgetmapping_detail"),
    path("budget-mappings/<int:pk>/edit/", views.budgetmapping_edit, name="budgetmapping_edit"),
    path("budget-mappings/<int:pk>/delete/", views.budgetmapping_delete,
         name="budgetmapping_delete"),
]
