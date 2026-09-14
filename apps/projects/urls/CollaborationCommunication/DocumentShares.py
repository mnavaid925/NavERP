"""Projects 7.9 — DocumentShare routes (prefix ``shared-documents/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``shared-documents/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("shared-documents/", views.dsh_list, name="dsh_list"),
    path("shared-documents/add/", views.dsh_create, name="dsh_create"),
    path("shared-documents/<int:pk>/", views.dsh_detail, name="dsh_detail"),
    path("shared-documents/<int:pk>/edit/", views.dsh_edit, name="dsh_edit"),
    path("shared-documents/<int:pk>/delete/", views.dsh_delete, name="dsh_delete"),
    path("shared-documents/<int:pk>/revoke/", views.dsh_revoke, name="dsh_revoke"),
    path("shared-documents/<int:pk>/claim/", views.dsh_claim, name="dsh_claim"),
    path("shared-documents/<int:pk>/release/", views.dsh_release, name="dsh_release"),
]
