"""SCM 4.9 Quality Management — QualityInspection routes (prefix ``inspections/``).

The literal ``inspections/add/`` MUST precede ``inspections/<int:pk>/`` — Django is first-match-
wins, and while ``<int:pk>`` would not itself match "add", keeping the literal first is the rule
this URLconf follows everywhere. The ten verb routes all sit UNDER ``<int:pk>/``, so none of them
can be swallowed. ``inspections/`` is a distinct first segment from 4.1's ``receipts/`` and 4.9's
own ``inspection-plans/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("inspections/", views.qualityinspection_list, name="qualityinspection_list"),
    path("inspections/add/", views.qualityinspection_create, name="qualityinspection_create"),
    path("inspections/<int:pk>/", views.qualityinspection_detail, name="qualityinspection_detail"),
    path("inspections/<int:pk>/edit/", views.qualityinspection_edit,
         name="qualityinspection_edit"),
    path("inspections/<int:pk>/delete/", views.qualityinspection_delete,
         name="qualityinspection_delete"),
    # Lifecycle + the result snapshot — no stock effect.
    path("inspections/<int:pk>/generate-results/", views.qualityinspection_generate_results,
         name="qualityinspection_generate_results"),
    path("inspections/<int:pk>/start/", views.qualityinspection_start,
         name="qualityinspection_start"),
    path("inspections/<int:pk>/complete/", views.qualityinspection_complete,
         name="qualityinspection_complete"),
    path("inspections/<int:pk>/hold/", views.qualityinspection_hold,
         name="qualityinspection_hold"),
    path("inspections/<int:pk>/resume/", views.qualityinspection_resume,
         name="qualityinspection_resume"),
    path("inspections/<int:pk>/cancel/", views.qualityinspection_cancel,
         name="qualityinspection_cancel"),
    # Privileged: the usage decision and the two lot-status flips (which post NO StockMove).
    path("inspections/<int:pk>/decide/", views.qualityinspection_decide,
         name="qualityinspection_decide"),
    path("inspections/<int:pk>/quarantine/", views.qualityinspection_quarantine,
         name="qualityinspection_quarantine"),
    path("inspections/<int:pk>/release-lot/", views.qualityinspection_release_lot,
         name="qualityinspection_release_lot"),
    # Compute-then-convert: proposes an NCR, once only.
    path("inspections/<int:pk>/raise-ncr/", views.qualityinspection_raise_ncr,
         name="qualityinspection_raise_ncr"),
]
