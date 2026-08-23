"""Inventory 5.8 Lot & Serial Number Tracking — FEFO board route (computed page)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("fefo-board/", views.fefo_board, name="fefo_board"),
]
