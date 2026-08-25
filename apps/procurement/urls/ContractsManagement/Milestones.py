"""Procurement 6.8 Contract Management — ContractMilestone + renewal board urlconf.

``milestones/`` and ``renewals/`` are distinct first segments in the flat app-level
route list; the completion verb carries a ``next`` POST target so both the contract
page and the register can return the user where they started.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal segments first — Django is first-match-wins.
    path("milestones/", views.milestone_list, name="milestone_list"),
    path("milestones/add/", views.milestone_create, name="milestone_create"),
    path("renewals/", views.renewals_board, name="renewals_board"),
    path("renewals/run/", views.renewals_run, name="renewals_run"),
    path("milestones/<int:pk>/edit/", views.milestone_edit, name="milestone_edit"),
    path("milestones/<int:pk>/complete/", views.milestone_complete,
         name="milestone_complete"),
    path("milestones/<int:pk>/delete/", views.milestone_delete,
         name="milestone_delete"),
]
