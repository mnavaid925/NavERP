"""Inventory 5.1 Product & Catalog Management — the module landing route."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("", views.overview, name="overview"),
]
