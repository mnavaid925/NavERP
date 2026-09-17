"""Projects 7.13 Agile & Scrum Management — Sprint URLs.
"""
from django.urls import path

from apps.projects.views.AgileScrumManagement import Sprints as views

urlpatterns = [
    path("agile/sprints/", views.spt_list, name="spt_list"),
    path("agile/sprints/add/", views.spt_create, name="spt_create"),
    path("agile/sprints/<int:pk>/", views.spt_detail, name="spt_detail"),
    path("agile/sprints/<int:pk>/edit/", views.spt_edit, name="spt_edit"),
    path("agile/sprints/<int:pk>/delete/", views.spt_delete, name="spt_delete"),
    path("agile/sprints/<int:pk>/start/", views.spt_start, name="spt_start"),
    path("agile/sprints/<int:pk>/complete/", views.spt_complete, name="spt_complete"),
    path("agile/sprints/<int:pk>/cancel/", views.spt_cancel, name="spt_cancel"),
]
