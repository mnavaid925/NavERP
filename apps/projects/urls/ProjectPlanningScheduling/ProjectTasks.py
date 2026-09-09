"""Projects 7.2 — ProjectTask routes (prefix ``tasks/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("tasks/tree/", views.tsk_tree, name="tsk_tree"),
    path("tasks/", views.tsk_list, name="tsk_list"),
    path("tasks/add/", views.tsk_create, name="tsk_create"),
    path("tasks/<int:pk>/", views.tsk_detail, name="tsk_detail"),
    path("tasks/<int:pk>/edit/", views.tsk_edit, name="tsk_edit"),
    path("tasks/<int:pk>/delete/", views.tsk_delete, name="tsk_delete"),
]
