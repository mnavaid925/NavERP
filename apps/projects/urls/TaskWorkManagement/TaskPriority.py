"""Projects 7.8 — TaskPriority route (first segment ``task-priority/``).

A single literal GET route — the computed priority lens takes no pk. The first segment
``task-priority/`` is a disjoint literal from every other module's in this app (§4 of the 7.8
contract), so nothing here can shadow another module's namespace.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("task-priority/", views.task_priority, name="task_priority"),
]
