"""Projects 7.12 Portfolio & Program Management — ProgramDependency URLs.
"""
from django.urls import path

from apps.projects.views.PortfolioProgramManagement import ProgramDependencies as views

urlpatterns = [
    path("program-dependencies/", views.pdep_list, name="pdep_list"),
    path("program-dependencies/add/", views.pdep_create, name="pdep_create"),
    path("program-dependencies/<int:pk>/", views.pdep_detail, name="pdep_detail"),
    path("program-dependencies/<int:pk>/edit/", views.pdep_edit, name="pdep_edit"),
    path("program-dependencies/<int:pk>/delete/", views.pdep_delete, name="pdep_delete"),
    path("program-dependencies/<int:pk>/clear/", views.pdep_clear, name="pdep_clear"),
    path("program-dependencies/<int:pk>/reopen/", views.pdep_reopen, name="pdep_reopen"),
]
