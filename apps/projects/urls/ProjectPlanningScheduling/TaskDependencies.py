"""Projects 7.2 — TaskDependency routes (prefix ``dependencies/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("dependencies/", views.dep_list, name="dep_list"),
    path("dependencies/add/", views.dep_create, name="dep_create"),
    path("dependencies/<int:pk>/", views.dep_detail, name="dep_detail"),
    path("dependencies/<int:pk>/edit/", views.dep_edit, name="dep_edit"),
    path("dependencies/<int:pk>/delete/", views.dep_delete, name="dep_delete"),
]
