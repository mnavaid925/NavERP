"""Projects 7.13 Agile & Scrum Management — ProjectEpic URLs.
"""
from django.urls import path

from apps.projects.views.AgileScrumManagement import ProjectEpics as views

urlpatterns = [
    path("agile/epics/", views.epc_list, name="epc_list"),
    path("agile/epics/add/", views.epc_create, name="epc_create"),
    path("agile/epics/<int:pk>/", views.epc_detail, name="epc_detail"),
    path("agile/epics/<int:pk>/edit/", views.epc_edit, name="epc_edit"),
    path("agile/epics/<int:pk>/delete/", views.epc_delete, name="epc_delete"),
]
