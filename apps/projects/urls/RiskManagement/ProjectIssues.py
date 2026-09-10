"""Projects 7.5 — ProjectIssue routes (prefix ``issues/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``issues/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("issues/", views.iss_list, name="iss_list"),
    path("issues/add/", views.iss_create, name="iss_create"),
    path("issues/<int:pk>/", views.iss_detail, name="iss_detail"),
    path("issues/<int:pk>/edit/", views.iss_edit, name="iss_edit"),
    path("issues/<int:pk>/delete/", views.iss_delete, name="iss_delete"),
    path("issues/<int:pk>/escalate/", views.iss_escalate, name="iss_escalate"),
    path("issues/<int:pk>/resolve/", views.iss_resolve, name="iss_resolve"),
    path("issues/<int:pk>/close/", views.iss_close, name="iss_close"),
]
