"""Inventory 5.15 — DefectReport URL patterns (prefix ``defect-reports/``).

Literal routes precede the ``<int:pk>`` ones (first-match-wins); verbs are POST-only.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("defect-reports/", views.defectreport_list, name="defectreport_list"),
    path("defect-reports/add/", views.defectreport_create, name="defectreport_create"),
    path("defect-reports/<int:pk>/", views.defectreport_detail, name="defectreport_detail"),
    path("defect-reports/<int:pk>/edit/", views.defectreport_edit, name="defectreport_edit"),
    path("defect-reports/<int:pk>/delete/", views.defectreport_delete, name="defectreport_delete"),
    path("defect-reports/<int:pk>/writeoff/", views.defectreport_writeoff, name="defectreport_writeoff"),
    path("defect-reports/<int:pk>/close/", views.defectreport_close, name="defectreport_close"),
]
