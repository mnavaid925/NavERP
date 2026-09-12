"""Projects 7.8 — GanttTimeline route (first segment ``gantt-timeline/``).

A single literal GET route — the computed timeline takes no pk (the window adjusters
``?start=``/``?end=`` ride the query string). The first segment ``gantt-timeline/`` is a
disjoint literal from every other module's in this app (§4 of the 7.8 contract), so nothing
here can shadow another module's namespace.
"""
from django.urls import path

# Direct sub-module import: the views package re-export lands in the Integrate step (the
# sibling modules' ``from apps.projects import views`` idiom resolves through it).
from apps.projects.views.TaskWorkManagement.GanttTimeline import gantt_timeline

urlpatterns = [
    path("gantt-timeline/", gantt_timeline, name="gantt_timeline"),
]
