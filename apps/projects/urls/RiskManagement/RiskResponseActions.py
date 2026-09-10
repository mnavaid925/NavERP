"""Projects 7.5 — RiskResponseAction routes (prefix ``responses/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``responses/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("responses/", views.rra_list, name="rra_list"),
    path("responses/add/", views.rra_create, name="rra_create"),
    path("responses/<int:pk>/", views.rra_detail, name="rra_detail"),
    path("responses/<int:pk>/edit/", views.rra_edit, name="rra_edit"),
    path("responses/<int:pk>/delete/", views.rra_delete, name="rra_delete"),
    path("responses/<int:pk>/complete/", views.rra_complete, name="rra_complete"),
]
