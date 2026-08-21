"""Inventory 5.1 Product & Catalog Management — ItemAttribute routes (prefix ``attributes/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("attributes/", views.itemattribute_list, name="itemattribute_list"),
    path("attributes/add/", views.itemattribute_create, name="itemattribute_create"),
    path("attributes/<int:pk>/", views.itemattribute_detail, name="itemattribute_detail"),
    path("attributes/<int:pk>/edit/", views.itemattribute_edit, name="itemattribute_edit"),
    path("attributes/<int:pk>/delete/", views.itemattribute_delete, name="itemattribute_delete"),
]
