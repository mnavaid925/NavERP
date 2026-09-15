"""Projects 7.10 - ProjectDocument routes (prefix ``documents/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones - Django is first-match-wins. The first
segment ``documents/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("documents/", views.pdm_list, name="pdm_list"),
    path("documents/add/", views.pdm_create, name="pdm_create"),
    path("documents/<int:pk>/", views.pdm_detail, name="pdm_detail"),
    path("documents/<int:pk>/edit/", views.pdm_edit, name="pdm_edit"),
    path("documents/<int:pk>/delete/", views.pdm_delete, name="pdm_delete"),
    path("documents/<int:pk>/checkout/", views.pdm_checkout, name="pdm_checkout"),
    path("documents/<int:pk>/checkin/", views.pdm_checkin, name="pdm_checkin"),
    path("documents/<int:pk>/archive/", views.pdm_archive, name="pdm_archive"),
    path("documents/<int:pk>/hold/", views.pdm_hold, name="pdm_hold"),
    path("documents/<int:pk>/release/", views.pdm_release, name="pdm_release"),
    path("documents/<int:pk>/reindex/", views.pdm_reindex, name="pdm_reindex"),
]
