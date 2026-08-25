"""Inventory 5.18 — GLPostRule routes (prefix ``gl-post-rules``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("gl-post-rules/", views.glpostrule_list, name="glpostrule_list"),
    path("gl-post-rules/add/", views.glpostrule_create, name="glpostrule_create"),
    path("gl-post-rules/<int:pk>/", views.glpostrule_detail, name="glpostrule_detail"),
    path("gl-post-rules/<int:pk>/edit/", views.glpostrule_edit, name="glpostrule_edit"),
    path("gl-post-rules/<int:pk>/delete/", views.glpostrule_delete, name="glpostrule_delete"),
]
