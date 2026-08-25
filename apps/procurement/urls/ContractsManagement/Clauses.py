"""Procurement 6.8 Contract Management — ContractClause urlconf.

Every route carries the ``clauses/`` first segment: these patterns concatenate into
one flat app-level list where Django is first-match-wins, so an unprefixed ``add/``
here would shadow every later sub-module's ``add/``.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal segments first — Django is first-match-wins.
    path("clauses/", views.clause_list, name="clause_list"),
    path("clauses/add/", views.clause_create, name="clause_create"),
    path("clauses/<int:pk>/", views.clause_detail, name="clause_detail"),
    path("clauses/<int:pk>/edit/", views.clause_edit, name="clause_edit"),
    path("clauses/<int:pk>/delete/", views.clause_delete, name="clause_delete"),
]
