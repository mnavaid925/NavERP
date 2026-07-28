"""SCM 4.9 Quality Management — CapaAction routes (prefix ``capa/``).

``capa/`` is a distinct first segment from 4.2's ``catalogs/`` and 4.1's ``categories/`` — Django
matches whole path segments, not string prefixes.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("capa/", views.capaaction_list, name="capaaction_list"),
    path("capa/add/", views.capaaction_create, name="capaaction_create"),
    path("capa/<int:pk>/", views.capaaction_detail, name="capaaction_detail"),
    path("capa/<int:pk>/edit/", views.capaaction_edit, name="capaaction_edit"),
    path("capa/<int:pk>/delete/", views.capaaction_delete, name="capaaction_delete"),
    path("capa/<int:pk>/start/", views.capaaction_start, name="capaaction_start"),
    path("capa/<int:pk>/progress/", views.capaaction_progress, name="capaaction_progress"),
    path("capa/<int:pk>/implement/", views.capaaction_implement, name="capaaction_implement"),
    # The formal effectiveness sign-off — tenant-admin gated in the view.
    path("capa/<int:pk>/verify/", views.capaaction_verify, name="capaaction_verify"),
    path("capa/<int:pk>/cancel/", views.capaaction_cancel, name="capaaction_cancel"),
]
