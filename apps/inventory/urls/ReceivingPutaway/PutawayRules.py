"""Inventory 5.4 Receiving & Putaway — routes (prefixes ``putaway-rules/`` and the computed
``putaway-suggestions/`` page). Literals before ``<int:pk>``, per the house first-match rule."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("putaway-suggestions/", views.putaway_suggestions, name="putaway_suggestions"),
    path("putaway-rules/", views.putawayrule_list, name="putawayrule_list"),
    path("putaway-rules/add/", views.putawayrule_create, name="putawayrule_create"),
    path("putaway-rules/<int:pk>/", views.putawayrule_detail, name="putawayrule_detail"),
    path("putaway-rules/<int:pk>/edit/", views.putawayrule_edit, name="putawayrule_edit"),
    path("putaway-rules/<int:pk>/delete/", views.putawayrule_delete, name="putawayrule_delete"),
]
