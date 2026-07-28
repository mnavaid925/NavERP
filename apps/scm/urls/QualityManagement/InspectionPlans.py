"""SCM 4.9 Quality Management — InspectionPlan routes (prefix ``inspection-plans/``).

Literal ``add/`` before ``<int:pk>/``. ``inspection-plans/`` is a distinct first segment from 4.9's
own ``inspections/`` — Django matches the whole pattern, not a prefix.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("inspection-plans/", views.inspectionplan_list, name="inspectionplan_list"),
    path("inspection-plans/add/", views.inspectionplan_create, name="inspectionplan_create"),
    path("inspection-plans/<int:pk>/", views.inspectionplan_detail, name="inspectionplan_detail"),
    path("inspection-plans/<int:pk>/edit/", views.inspectionplan_edit, name="inspectionplan_edit"),
    path("inspection-plans/<int:pk>/delete/", views.inspectionplan_delete,
         name="inspectionplan_delete"),
]
