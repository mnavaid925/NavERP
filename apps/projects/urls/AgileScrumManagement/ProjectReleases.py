"""Projects 7.13 Agile & Scrum Management — ProjectRelease URLs.
"""
from django.urls import path

from apps.projects.views.AgileScrumManagement import ProjectReleases as views

urlpatterns = [
    path("agile/releases/", views.rel_list, name="rel_list"),
    path("agile/releases/add/", views.rel_create, name="rel_create"),
    path("agile/releases/<int:pk>/", views.rel_detail, name="rel_detail"),
    path("agile/releases/<int:pk>/edit/", views.rel_edit, name="rel_edit"),
    path("agile/releases/<int:pk>/delete/", views.rel_delete, name="rel_delete"),
    path("agile/releases/<int:pk>/publish/", views.rel_publish, name="rel_publish"),
]
