"""Projects 7.10 — ProjectFolder routes (prefix ``doc-folders/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``doc-folders/`` is a disjoint literal from every other module's in this app (7.4 owns
``revisions/``, so the revision log mounts at ``document-revisions/``).
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("doc-folders/", views.pfd_list, name="pfd_list"),
    path("doc-folders/add/", views.pfd_create, name="pfd_create"),
    path("doc-folders/<int:pk>/", views.pfd_detail, name="pfd_detail"),
    path("doc-folders/<int:pk>/edit/", views.pfd_edit, name="pfd_edit"),
    path("doc-folders/<int:pk>/delete/", views.pfd_delete, name="pfd_delete"),
    path("doc-folders/<int:pk>/archive/", views.pfd_archive, name="pfd_archive"),
]
