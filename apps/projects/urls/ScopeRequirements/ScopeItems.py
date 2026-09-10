"""Projects 7.7 — ScopeItem routes (prefix ``scope-items/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``scope-items/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("scope-items/", views.sci_list, name="sci_list"),
    path("scope-items/add/", views.sci_create, name="sci_create"),
    path("scope-items/<int:pk>/", views.sci_detail, name="sci_detail"),
    path("scope-items/<int:pk>/edit/", views.sci_edit, name="sci_edit"),
    path("scope-items/<int:pk>/delete/", views.sci_delete, name="sci_delete"),
    path("scope-items/<int:pk>/validate/", views.sci_validate, name="sci_validate"),
    path("scope-items/<int:pk>/realize/", views.sci_realize, name="sci_realize"),
    path("scope-items/<int:pk>/retire/", views.sci_retire, name="sci_retire"),
]
