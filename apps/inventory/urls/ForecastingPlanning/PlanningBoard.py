"""Inventory 5.13 Inventory Forecasting & Planning — planning board routes (computed page + gated apply)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("planning-board/", views.planning_board, name="planning_board"),
    path("planning-board/<int:pk>/apply/", views.planning_apply_computed,
         name="planning_apply_computed"),
]
