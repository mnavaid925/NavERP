"""Projects 7.1 — ProjectStakeholder routes (prefix ``stakeholders/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("stakeholders/", views.pst_list, name="pst_list"),
    path("stakeholders/add/", views.pst_create, name="pst_create"),
    path("stakeholders/<int:pk>/", views.pst_detail, name="pst_detail"),
    path("stakeholders/<int:pk>/edit/", views.pst_edit, name="pst_edit"),
    path("stakeholders/<int:pk>/delete/", views.pst_delete, name="pst_delete"),
]
