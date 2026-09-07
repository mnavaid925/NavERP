"""Projects 7.1 — Project routes (prefix ``projects/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("projects/", views.prj_list, name="prj_list"),
    path("projects/add/", views.prj_create, name="prj_create"),
    path("projects/<int:pk>/", views.prj_detail, name="prj_detail"),
    path("projects/<int:pk>/edit/", views.prj_edit, name="prj_edit"),
    path("projects/<int:pk>/delete/", views.prj_delete, name="prj_delete"),
    path("projects/<int:pk>/submit-charter/", views.prj_submit_charter, name="prj_submit_charter"),
    path("projects/<int:pk>/approve-charter/", views.prj_approve_charter,
         name="prj_approve_charter"),
]
