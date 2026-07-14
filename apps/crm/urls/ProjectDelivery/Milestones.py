"""CRM 1.8 Project & Delivery Management — Milestones URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Milestones (1.8)
    path("milestones/", views.crmmilestone_list, name="crmmilestone_list"),
    path("milestones/add/", views.crmmilestone_create, name="crmmilestone_create"),
    path("milestones/<int:pk>/", views.crmmilestone_detail, name="crmmilestone_detail"),
    path("milestones/<int:pk>/edit/", views.crmmilestone_edit, name="crmmilestone_edit"),
    path("milestones/<int:pk>/delete/", views.crmmilestone_delete, name="crmmilestone_delete"),
    path("milestones/<int:pk>/move/", views.crmmilestone_move, name="crmmilestone_move"),
]
