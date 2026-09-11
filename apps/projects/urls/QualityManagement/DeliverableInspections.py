"""Projects 7.6 — DeliverableInspection routes (prefix ``inspections/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``inspections/`` is a disjoint literal from every other module's in this app (and from
scm 4.9's own inspection routes — that app's urlconf is namespaced ``scm:``, so no cross-app
collision is possible; the disjointness that matters is inside ``projects:``).
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("inspections/", views.qci_list, name="qci_list"),
    path("inspections/add/", views.qci_create, name="qci_create"),
    path("inspections/<int:pk>/", views.qci_detail, name="qci_detail"),
    path("inspections/<int:pk>/edit/", views.qci_edit, name="qci_edit"),
    path("inspections/<int:pk>/delete/", views.qci_delete, name="qci_delete"),
    path("inspections/<int:pk>/record/", views.qci_record, name="qci_record"),
    path("inspections/<int:pk>/accept/", views.qci_accept, name="qci_accept"),
    path("inspections/<int:pk>/reject/", views.qci_reject, name="qci_reject"),
]
