"""Inventory 5.10 Returns Management — DispositionRoutingRule URL patterns."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("disposition-rules/", views.dispositionrule_list, name="dispositionrule_list"),
    path("disposition-rules/add/", views.dispositionrule_create, name="dispositionrule_create"),
    path("disposition-rules/<int:pk>/", views.dispositionrule_detail, name="dispositionrule_detail"),
    path("disposition-rules/<int:pk>/edit/", views.dispositionrule_edit, name="dispositionrule_edit"),
    path("disposition-rules/<int:pk>/delete/", views.dispositionrule_delete, name="dispositionrule_delete"),
]
