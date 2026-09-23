"""Projects 7.19 — ProjectCustomField URLs."""
from django.urls import path

from apps.projects.views.MasterDataConfiguration import ProjectCustomFields as views

urlpatterns = [
    path("master-data/custom-fields/", views.pcf_list, name="pcf_list"),
    path("master-data/custom-fields/add/", views.pcf_create, name="pcf_create"),
    path("master-data/custom-fields/<int:pk>/", views.pcf_detail, name="pcf_detail"),
    path("master-data/custom-fields/<int:pk>/edit/", views.pcf_edit, name="pcf_edit"),
    path("master-data/custom-fields/<int:pk>/delete/", views.pcf_delete, name="pcf_delete"),
    path("master-data/custom-fields/<int:pk>/toggle/", views.pcf_toggle_active, name="pcf_toggle_active"),
]
