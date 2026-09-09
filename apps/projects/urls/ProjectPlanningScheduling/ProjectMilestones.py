"""Projects 7.2 — ProjectMilestone routes (prefix ``milestones/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("milestones/", views.mst_list, name="mst_list"),
    path("milestones/add/", views.mst_create, name="mst_create"),
    path("milestones/<int:pk>/", views.mst_detail, name="mst_detail"),
    path("milestones/<int:pk>/edit/", views.mst_edit, name="mst_edit"),
    path("milestones/<int:pk>/delete/", views.mst_delete, name="mst_delete"),
    path("milestones/<int:pk>/achieve/", views.mst_achieve, name="mst_achieve"),
]
