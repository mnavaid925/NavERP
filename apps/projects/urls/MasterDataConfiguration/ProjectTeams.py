"""Projects 7.19 — ProjectTeam URLs."""
from django.urls import path

from apps.projects.views.MasterDataConfiguration import ProjectTeams as views

urlpatterns = [
    path("master-data/teams/", views.pte_list, name="pte_list"),
    path("master-data/teams/add/", views.pte_create, name="pte_create"),
    path("master-data/teams/<int:pk>/", views.pte_detail, name="pte_detail"),
    path("master-data/teams/<int:pk>/edit/", views.pte_edit, name="pte_edit"),
    path("master-data/teams/<int:pk>/delete/", views.pte_delete, name="pte_delete"),
    path("master-data/teams/<int:pk>/members/add/", views.pte_add_member, name="pte_add_member"),
    path("master-data/teams/<int:team_pk>/members/<int:pk>/delete/", views.pte_remove_member, name="pte_remove_member"),
]
