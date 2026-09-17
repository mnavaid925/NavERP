"""Projects 7.13 Agile & Scrum Management — SprintImpediment URLs.
"""
from django.urls import path

from apps.projects.views.AgileScrumManagement import SprintImpediments as views

urlpatterns = [
    path("agile/impediments/", views.imp_list, name="imp_list"),
    path("agile/impediments/add/", views.imp_create, name="imp_create"),
    path("agile/impediments/<int:pk>/", views.imp_detail, name="imp_detail"),
    path("agile/impediments/<int:pk>/edit/", views.imp_edit, name="imp_edit"),
    path("agile/impediments/<int:pk>/delete/", views.imp_delete, name="imp_delete"),
    path("agile/impediments/<int:pk>/resolve/", views.imp_resolve, name="imp_resolve"),
]
