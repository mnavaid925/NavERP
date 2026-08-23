"""Inventory 5.10 Returns Management — ReturnInspection URL patterns."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("inspections/", views.returninspection_list, name="returninspection_list"),
    path("inspections/add/", views.returninspection_create, name="returninspection_create"),
    path("inspections/<int:pk>/", views.returninspection_detail, name="returninspection_detail"),
    path("inspections/<int:pk>/edit/", views.returninspection_edit, name="returninspection_edit"),
    path("inspections/<int:pk>/delete/", views.returninspection_delete, name="returninspection_delete"),
]
