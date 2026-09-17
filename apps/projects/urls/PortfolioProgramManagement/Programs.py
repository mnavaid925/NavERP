"""Projects 7.12 Portfolio & Program Management — Program URLs.
"""
from django.urls import path

from apps.projects.views.PortfolioProgramManagement import Programs as views

urlpatterns = [
    path("programs/", views.pgm_list, name="pgm_list"),
    path("programs/add/", views.pgm_create, name="pgm_create"),
    path("programs/<int:pk>/", views.pgm_detail, name="pgm_detail"),
    path("programs/<int:pk>/edit/", views.pgm_edit, name="pgm_edit"),
    path("programs/<int:pk>/delete/", views.pgm_delete, name="pgm_delete"),
]
