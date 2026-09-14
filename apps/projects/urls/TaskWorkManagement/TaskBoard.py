"""Projects 7.8 — TaskBoard route (first segment ``task-board/``).

A single literal GET route — the computed board takes no pk. The first segment
``task-board/`` is a disjoint literal from every other module's in this app (§4 of the 7.8
contract), so nothing here can shadow another module's namespace.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("task-board/", views.task_board, name="task_board"),
]
