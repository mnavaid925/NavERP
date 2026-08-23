"""Inventory 5.10 Returns Management — Returns Workbench URL patterns."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("returns-workbench/", views.returns_workbench, name="returns_workbench"),
]
