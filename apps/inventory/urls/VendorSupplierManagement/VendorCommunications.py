"""Inventory 5.2 Vendor / Supplier Management — VendorCommunication routes (prefix
``vendor-communications/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("vendor-communications/", views.vendorcommunication_list, name="vendorcommunication_list"),
    path("vendor-communications/add/", views.vendorcommunication_create, name="vendorcommunication_create"),
    path("vendor-communications/<int:pk>/", views.vendorcommunication_detail, name="vendorcommunication_detail"),
    path("vendor-communications/<int:pk>/edit/", views.vendorcommunication_edit, name="vendorcommunication_edit"),
    path("vendor-communications/<int:pk>/delete/", views.vendorcommunication_delete, name="vendorcommunication_delete"),
]
