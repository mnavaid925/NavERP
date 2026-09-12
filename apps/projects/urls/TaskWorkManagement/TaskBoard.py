"""Projects 7.8 — TaskBoard route (first segment ``task-board/``).

A single literal GET route — the computed board takes no pk. The first segment
``task-board/`` is a disjoint literal from every other module's in this app (§4 of the 7.8
contract), so nothing here can shadow another module's namespace.
"""
from django.urls import path

# Direct sub-module import: the views package re-export lands in the Integrate step (the
# sibling modules' ``from apps.projects import views`` idiom resolves through it).
from apps.projects.views.TaskWorkManagement.TaskBoard import task_board

urlpatterns = [
    path("task-board/", task_board, name="task_board"),
]
