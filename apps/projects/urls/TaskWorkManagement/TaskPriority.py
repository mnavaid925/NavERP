"""Projects 7.8 — TaskPriority route (first segment ``task-priority/``).

A single literal GET route — the computed priority lens takes no pk. The first segment
``task-priority/`` is a disjoint literal from every other module's in this app (§4 of the 7.8
contract), so nothing here can shadow another module's namespace.
"""
from django.urls import path

# Direct sub-module import: the views package re-export lands in the Integrate step (the
# sibling modules' ``from apps.projects import views`` idiom resolves through it).
from apps.projects.views.TaskWorkManagement.TaskPriority import task_priority

urlpatterns = [
    path("task-priority/", task_priority, name="task_priority"),
]
