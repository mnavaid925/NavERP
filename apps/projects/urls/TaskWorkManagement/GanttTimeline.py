"""Projects 7.8 — GanttTimeline route (first segment ``gantt-timeline/``).

A single literal GET route — the computed timeline takes no pk (the window adjusters
``?start=``/``?end=`` ride the query string). The first segment ``gantt-timeline/`` is a
disjoint literal from every other module's in this app (§4 of the 7.8 contract), so nothing
here can shadow another module's namespace.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("gantt-timeline/", views.gantt_timeline, name="gantt_timeline"),
]
